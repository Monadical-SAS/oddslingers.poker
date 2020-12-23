import random
import logging
from uuid import UUID
from typing import Union, List

from decimal import Decimal
from datetime import timedelta

from django.db.models import QuerySet, Q, Count
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

from banker.mutations import buy_chips, create_transfer

from oddslingers.mutations import execute_mutations
from oddslingers.models import User
from oddslingers.utils import debug_print_info

from poker.constants import (
    PlayingState, TABLE_TYPES, HIDE_TABLES_AFTER_N_HANDS,
    BLINDS_SCHEDULE, TOURNEY_STARTING_CHIPS, THRESHOLD_BB_FOR_BOTS,
)
from poker.models import (
    PokerTable, Player, Freezeout, PokerTournament
)
from poker.controllers import GameController, controller_for_table
from poker.bot_personalities import PERSONALITIES

logger = logging.getLogger('poker')



TABLE_NOUNS = [
    'Jamboree', 'Shindig', 'Showdown', 'Blowout', 'Bash', 'Clash', 'Brawl',
    'Battle', 'Altercation', 'Fracas', 'Feud', 'Scuffle', 'Ruckus', 'Riot',
    'Uproar', 'Wrangle', 'Rumble', 'Quarrel', 'Broil', 'Fight', 'Rumpus',
    'Battle Royale', 'Tumult', 'Fray', 'Donnybrook', 'Disorder', 'Row',
    'Encounter', 'Discord', 'Collision', 'Impact', 'Skirmish', 'Smash',
    'Wallop', 'Shock', 'Jolt', 'Tangle', 'Scrap', 'Combat', 'Encounter',
    'Disco', 'Hoedown', 'Jam', 'Tango', 'Conga', 'Boogie', 'Waltz', 'Conga',
    'Rhumba', 'Gambol', 'Samba', 'Strut', 'Bistro', 'Tavern', 'Saloon',
    'Hall', 'Joint', 'Roadhouse', 'Dive', 'Honky-Tonk', 'House', 'Den',
]


def public_games(user: User=None) -> QuerySet:
    """
    Get all cash tables that should appear on the games page:
    excludes:
        - mock, archived, and tutorial tables
        - private tables
        - custom tables with nobody seated
        - tournaments
        - empty tables that have > HIDE_TABLES_AFTER_N_HANDS
    """
    n_seated_players = Count('player', filter=Q(player__seated=True))
    new_system_created = (
        Q(created_by=None) & Q(hand_number__lt=HIDE_TABLES_AFTER_N_HANDS)
    )
    all_games = PokerTable.objects\
                          .filter(is_mock=False,
                                  is_archived=False,
                                  is_private=False,
                                  is_tutorial=False,
                                  tournament__isnull=True)\
                          .annotate(n_seated=n_seated_players)\
                          .filter((new_system_created) | Q(n_seated__gt=0))\
                          .order_by('-modified', 'n_seated')

    if user:
        return all_games.filter(player__user_id=user.id)

    return all_games


def has_recent_human_activity(table: PokerTable, minutes: int=10) -> bool:
    # print(
    #     f'>has_recent_human_activity({table.name}, {minutes})\n'
    #     f'last_human_action_timestamp {table.last_human_action_timestamp}'
    #     f' > recently {recently}: '
    #     f'{table.last_human_action_timestamp > recently}'
    # )
    if not table.last_human_action_timestamp:
        return False
    recently = timezone.now() - timedelta(minutes=minutes)
    return table.last_human_action_timestamp > recently


def private_games(user: User) -> QuerySet:
    """Get all tables only visible to players on those tables"""
    is_not_public = (
        Q(is_archived=True)
      | Q(is_tutorial=True)
      | Q(hand_number__gt=HIDE_TABLES_AFTER_N_HANDS)
    )
    return PokerTable.objects.filter(
        is_not_public,
        is_mock=False,
        player__user_id=user.id,
    )


def system_created_games(games: QuerySet=None) -> QuerySet:
    """
    Get all public tables that were automatically created by OddSlingers
    """
    return (games or public_games()).filter(created_by=None)


def featured_table(only=()) -> PokerTable:
    """
    Returns the highest stakes game that is currently running (active)
    if no games are actively running, returns a bot table with empty seats
    and a bb==2
    """

    public_tables = public_games()
    n_system_created = public_tables.filter(created_by=None).count()
    if n_system_created < settings.TABLES_PAGE_MINIMUM_TABLES:
        # populate tables page will all of the standard games
        make_new_bot_games()
        public_tables = public_games()

    # return the highest-stakes game with humans playing
    a_minute_ago = timezone.now() - timedelta(minutes=1)
    recently_active = public_tables\
        .filter(last_human_action_timestamp__gt=a_minute_ago)\
        .order_by('bb')\
        .only(*only).last()

    if recently_active:
        return recently_active

    # as a fallback, return a 1/2 table with seated players
    active = Count('player', filter=Q(player__playing_state_int=PlayingState.SITTING_IN.value))
    featured_table = (
        system_created_games()
        .annotate(n_active_players=active)
        .filter(bb=2, n_active_players__gt=2)
        .only(*only)
        .first()
    )

    if not featured_table:
        logger.error(
            'No 1/2 system created game was available to be featured_table',
            extra={
                'recently_active': recently_active,
                'all_system_created_games': list(system_created_games()),
                'one_two_games': list(system_created_games().filter(bb=2)),
            },
        )
        featured_table = (
            system_created_games().only(*only).first()
            or
            public_tables().last()
        )

    return featured_table


def featured_game() -> GameController:
    table = featured_table()
    assert table, 'featured_table returned None!'
    return controller_for_table(table)


def fuzzy_get_table(id: Union[UUID, str], only=()) -> PokerTable:
    try:
        qs = PokerTable.objects
        if only:
            qs = qs.only(*only)
        else:
            qs = qs.with_players().with_stats().with_chathistory()

        if isinstance(id, UUID):
            return qs.get(id=id)
        if isinstance(id, str):
            return qs.get(id__startswith=id)
        else:
            raise TypeError('Table id must be a UUID or str')
    except PokerTable.MultipleObjectsReturned:
        raise ValueError('More than one table found with that short_id.')
    except PokerTable.DoesNotExist:
        raise KeyError('Table with given id not found.')


def fuzzy_get_game(id: Union[UUID, str]) -> GameController:
    return controller_for_table(fuzzy_get_table(id), verbose=False)


BOT_USER_DEFAULTS = {'is_robot': True}

def BOT_PLAYER_DEFAULTS(table: PokerTable) -> dict:
    min_bbs = table.min_buyin // table.bb
    max_bbs = table.max_buyin // table.bb
    return {
        'stack': table.bb * random.randint(min_bbs, max_bbs),
        'seated': True,
        'playing_state': PlayingState.SITTING_IN,
        'auto_rebuy': random.choice((
            table.min_buyin,
            table.max_buyin,
            table.bb * random.randint(min_bbs, max_bbs),
        )),
    }


def get_or_create_bot_user(robot_name: str) -> User:
    created = False
    try:
        bot_user = User.objects.get(
            username=robot_name,
            is_robot=True
        )
    except User.DoesNotExist:
        created = True
        bot_user = User.objects.create_user(username=robot_name, is_robot=True)

    if created:
        execute_mutations(
            buy_chips(bot_user, 10000000)
        )

    return bot_user


def create_bot_player(table: PokerTable,
                      bot_user: User,
                      position: int) -> Player:
    defaults = BOT_PLAYER_DEFAULTS(table)
    bot_player, _ = Player.objects.get_or_create(
        table=table,
        user=bot_user,
        defaults={'position': position, **defaults}
    )
    # print('defaults', defaults)
    # print('created bot:', bot_player.__repr__())
    return bot_player


def robot_names_for_tournament(tournament: Freezeout) -> List[str]:
    return [
        username
        for username, personality in PERSONALITIES.items()
        if personality['stakes_range'][0] * 100 <= tournament.buyin_amt
        and tournament.buyin_amt <= personality['stakes_range'][1] * 100
    ]


def robot_names_for_table(table: PokerTable) -> List[str]:
    return [
        username
        for username, personality in PERSONALITIES.items()
        if personality['stakes_range'][0] <= table.bb
        and table.bb <= personality['stakes_range'][1]
    ]


def get_n_random_bot_names(game: Union[PokerTable, Freezeout], n: int) -> List[str]:
    if type(game) == Freezeout:
        robot_names = robot_names_for_tournament(game)
    else:
        robot_names = robot_names_for_table(game)
    return random.sample(robot_names, n)


def create_n_random_bot_players(table: PokerTable, n: int) -> List[Player]:
    bot_names = get_n_random_bot_names(table, n)
    positions = random.sample(range(table.num_seats), n)
    players = []
    for pos, bot_name in zip(positions, bot_names):
        bot_user = get_or_create_bot_user(bot_name)
        players.append(create_bot_player(table, bot_user, pos))
    return players


def make_game(name: str,
              defaults: dict=None,
              num_bots: int=0,
              with_user: User=None) -> GameController:

    created = True
    try:
        table = PokerTable.objects.get(name__iexact=name)
        created = False
    except PokerTable.DoesNotExist:
        table = PokerTable.objects.create_table(name, **defaults)

    if created and num_bots and table.bb <= THRESHOLD_BB_FOR_BOTS:
        create_n_random_bot_players(table, num_bots)

    controller = controller_for_table(table)

    # Don't call this before creating the bots or the tables won't auto start
    if with_user:
        controller.join_table(with_user.id)

    if created:
        # without an initial step() call, controller gets stuck
        #   in is_predeal forever
        controller.step()
        controller.commit()

    return controller


def make_tournament(defaults: dict, user: User) -> PokerTournament:
    if user.userbalance().balance >= defaults['min_buyin']:
        tournament = Freezeout.objects.create_tournament(
            name=defaults['table_name'],
            game_variant=defaults['table_type'],
            max_entrants=defaults['num_seats'],
            buyin_amt=defaults['min_buyin'],
            created_by=defaults['created_by'],
            tournament_admin=defaults['tournament_admin'],
            is_private=defaults['is_private'],
        )
        tournament.entrants.add(user)
        execute_mutations(create_transfer(
            user,
            tournament,
            tournament.buyin_amt,
            "Tournament buyin"
        ))
        return tournament
    raise ValueError('User has not enough funds')


def start_tournament(tournament: PokerTournament) -> PokerTable:
    created = True
    try:
        table = PokerTable.objects.get(name__iexact=tournament.name)
        created = False
    except PokerTable.DoesNotExist:
        table = PokerTable.objects.create_table(
            name=tournament.name,
            num_seats=tournament.max_entrants,
            sb=BLINDS_SCHEDULE[0][0],
            bb=BLINDS_SCHEDULE[0][1],
            table_type=tournament.game_variant,
            created_by=tournament.created_by,
            is_private=tournament.is_private,
            tournament=tournament
        )

    if created:
        for pos, entrant in enumerate(tournament.entrants.all()):
            Player.objects.get_or_create(
                user=entrant,
                table=table,
                defaults={
                    'stack': Decimal(TOURNEY_STARTING_CHIPS),
                    'position': pos,
                    'seated': True,
                    'playing_state_int': PlayingState.SITTING_IN.value
                }
            )

        controller = controller_for_table(table)
        controller.step()
        controller.commit()

    tournament.mark_as_started()
    return table


def make_new_bot_games() -> List[PokerTable]:
    """
    Create system_created_games as needed for each variant and bb combo
    """

    existing_tables = list(system_created_games().filter(tournament=None))

    # check to ensure enough required combinations of bb and variant
    expected_all = (2, 4, 6, 10, 20, 50, 100)
    expected_one = (200, 500, 1000)

    variants = [(table.bb, table.table_type) for table in existing_tables]
    missing = [
        (bb, table_type[0])
        for bb in expected_all
            for table_type in TABLE_TYPES
        if (bb, table_type[0]) not in variants
    ]
    stakes = [table.bb for table in existing_tables]

    missing += [
        (bb, random.choice(TABLE_TYPES)[0])
        for bb in expected_one
        if bb not in stakes
    ]

    if settings.IS_TESTING and len(missing):
        missing = [missing[0]]

    debug_print_info("Creating initial tables... site will be ready in 30sec")

    new_games = [
        make_bot_game(*variant, existing_tables).table
        for variant in missing
    ]
    assert system_created_games().exists(), (
        'system_created_games() must always exist '
        'after creating new bot games'
    )

    return new_games


def make_bot_game(bb: int, table_type: str,
                  existing_tables: List[PokerTable]=None) -> GameController:
    sb = bb / 2
    n_bots = random.choice([2, 3])

    if sb > 1 and table_type == 'PLO':
        n_bots = 0

    name = new_bot_table_name(bb, table_type)

    return make_game(name, num_bots=n_bots, defaults={
        'sb': sb,
        'bb': bb,
        'table_type': table_type,
        'min_buyin': 50*bb,
        'max_buyin': 200*bb,
        'num_seats': 6,
    })


def new_bot_table_name(bb: int, table_type: str) -> str:
    basename = f'{bb//2}/{bb} {table_type} {random.choice(TABLE_NOUNS)}'

    name = basename
    n = 2
    while PokerTable.objects.filter(name=name).exists():
        name = f'{basename} {n}'
        n += 1

    return name


def suspend_table(table: PokerTable, dump_id: UUID=None):
    from poker.megaphone import table_sockets

    table_sockets(table).filter(active=True).send_action(
        'NOTIFICATION', notifications=[{
            'type': 'admin',
            'bsStyle': 'danger',
            'title': 'Table suspended',
            'description': (
                'Player actions are temporarily paused, '
                'pending admin review of the table.  '
                'Redirecting you to Games list...'
            ),
            'redirect_url': reverse('Tables'),
            'delay': 4000,
        }],
    )

    # don't add stop_tablebeat here because suspend_tablebeat may need
    #   to be called from inside the tablebeat, and we dont want to
    #   suicide our own proc

