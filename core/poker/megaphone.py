from django.conf import settings

from oddslingers.utils import ExtendedEncoder
from sockets.models import Socket, SocketQuerySet


# the 'privado' keyword is added to any private gamestate in order so that
#   outgoing gamestates can be easily filtered on privacy (QA, etc)

def table_sockets(table) -> SocketQuerySet:
    """Get all sockets for a given table, including players and specators"""
    assert not table.is_mock, 'Should never get sockets for mock table'
    assert table and table.path, 'Table has no path to filter sockets'

    return Socket.objects.filter(path=table.path)


def tournament_sockets(tournament) -> SocketQuerySet:
    """Get all sockets for a given tournament, including entrants and spectators"""
    assert tournament and tournament.path, 'Tournament has no path to filter sockets'

    return Socket.objects.filter(path=tournament.path)


def player_sockets(player) -> SocketQuerySet:
    """Get private sockets for an active player at a table"""
    assert not player.is_mock, 'Should never get sockets for mock player'
    assert player.user_id, 'Player does not have an associated user'
    assert not player.table.is_mock, 'Should never get sockets for mock table'
    assert player.table and player.table.path, \
            'Table has no path to filter sockets'

    if player.is_robot:
        return Socket.objects.none()

    return table_sockets(player.table).filter(user_id=player.user_id)


def user_sockets(user, table) -> SocketQuerySet:
    """Get private sockets for an user spectating at a given table"""
    assert user.id, 'Player does not have an associated user'
    assert not table.is_mock, 'Should never get sockets for mock table'
    assert table and table.path, 'Table has no path to filter sockets'

    return table_sockets(table).filter(user_id=user.id)


def spectator_sockets(table, exclude_players=None) -> SocketQuerySet:
    """Get public sockets for all non-players connected to a given table"""
    if exclude_players:
        user_ids = [player.user.id for player in exclude_players]
        sockets = table_sockets(table).exclude(user_id__in=user_ids)
    else:
        seated_players = table.player_set.filter(seated=True)
        # print(*(f'{s.username}' for s in seated_players))
        seated_plyr_user_ids = seated_players.values_list('user_id', flat=True)
        # print(seated_plyr_user_ids)
        sockets = table_sockets(table).exclude(user_id__in=seated_plyr_user_ids)

    return sockets


def non_logged_in_spectator_sockets(table) -> SocketQuerySet:
    """Get public sockets for all non-logged in users connected to a
        given table"""
    sockets = spectator_sockets(table)
    return sockets.filter(user_id__isnull=True)


def logged_in_spectator_sockets(table,
                                distinct=False,
                                exclude_players=None) -> SocketQuerySet:
    """Get private sockets for all non-player logged
        in users connected to a given table"""
    sockets = spectator_sockets(table,
                                exclude_players).filter(user_id__isnull=False)
    if distinct:
        sockets = sockets.order_by('user_id').distinct('user_id')
    return sockets


def get_players_from_animations(gamestate, accessor):
    animations = gamestate.get('animations')
    #sidebets uses gamestate but not animations
    if animations:
        first_animation = animations[0]
        assert first_animation['type'] == 'SNAPTO', \
                'First animation on the animation queue must be a SNAPTO'
        player_ids = [player_id for player_id
                                in first_animation['value']['players']]

        last_animation = animations[-1]
        assert last_animation['type'] == 'SNAPTO', \
                'Last animation on the animation queue must be a SNAPTO'
        for player_id in last_animation['value']['players']:
            if player_id not in player_ids:
                player_ids.append(player_id)

        return [accessor.player_by_player_id(player_id)
                for player_id in player_ids]
    return accessor.seated_players()


def broadcast_to_sockets(accessor, subscribers, only_to_player=None):
    if only_to_player:
        gamestate = gamestate_json(accessor, only_to_player, subscribers)
        sockets = player_sockets(only_to_player)
        if sockets:
            return sockets.send_action(
                'UPDATE_GAMESTATE',
                privado=True,
                **gamestate,
            )
        else:
            return 0

    sent_count = 0
    sockets_and_gamestates = gamestates_for_sockets(
        accessor,
        subscribers,
    )

    for sockets, json_to_send in sockets_and_gamestates.items():
        sent_count += sockets.send_action(
            'UPDATE_GAMESTATE',
            **json_to_send
        )

    return sent_count


def gamestates_for_sockets(accessor, subscribers):
    output = {}
    # sanity check
    table_json = accessor.table_json()
    uncollected = accessor.current_uncollected()
    pot_sum = sum(pot['amt'] for pot in table_json['sidepot_summary'].values())
    if (pot_sum != table_json['total_pot']
            and pot_sum != table_json['total_pot'] - uncollected):
        raise Exception('ERROR: pot amounts do not add up.')

    # get the public gamestate to send it to all table viewers
    public_json_to_send = gamestate_json(accessor, None, subscribers)
    starting_players = get_players_from_animations(public_json_to_send, accessor)

    for player in starting_players:
        if player.is_robot:
            continue

        player_in_public = public_json_to_send['players'].get(str(player.id))
        if player_in_public and player_in_public.get('current'):
            if settings.DEBUG:
                import ipdb; ipdb.set_trace()
            else:
                raise Exception('Tried to send private json to spectators')
        json_to_send = gamestate_json(accessor, player, subscribers)
        json_to_send['privado'] = True
        output[player_sockets(player)] = json_to_send

    spectators = non_logged_in_spectator_sockets(accessor.table)
    # print('\n'.join(
    #     f'{s.path} {s.user.username if s.user else None} {s.active}'
    #     for s in spectators)
    # )
    public_json_to_send['privado'] = False
    output[spectators] = public_json_to_send

    logged_in_spectators = logged_in_spectator_sockets(accessor.table,
                                                       True,
                                                       starting_players)
    for spectator  in logged_in_spectators:
        new_json_to_send = gamestate_json(accessor,
                                          None,
                                          subscribers,
                                          spectator.user)

        new_json_to_send['privado'] = bool(new_json_to_send.get('sidebets'))
        output[user_sockets(spectator.user, accessor.table)] = new_json_to_send

    if accessor.table.tournament:
        tourney_sockets = tournament_sockets(accessor.table.tournament)
        output[tourney_sockets] = public_json_to_send

    return output


def gamestate_json(accessor, player=None, subscribers=None, spectator=None):
    json_to_send = {
        'players': accessor.players_json(player),
        'table': accessor.table_json(),
    }

    if subscribers is not None:
        for subscriber in subscribers:
            json_to_send.update(subscriber.updates_for_broadcast(player,
                                                                 spectator))

    # print(json_to_send)

    return ExtendedEncoder.convert_for_json(json_to_send)
