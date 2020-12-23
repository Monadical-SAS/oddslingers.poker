'''
In here you'll find personalities which will define how heuristics
are tuned for each bot. They have fun names like 'chaotic' and
'belligerent', and there is a comment explaining how each one affects
the robot's playstyle.

You can find the code that uses these parameters in poker/new_ai.py
'''


DEFAULT_BOT = {
    # range of max-buyins at which this bot can play
    'stakes_range': (1, 5000),
    'preflop': {
        'heads_up': {
            'btn': 0.85,
            'bb': 0.53,
        },
        'ring': {
            # at a 10-player table, UTG is 7
            #   (enable these if we add 7+ player tbls)
            # 7: 0.05,
            # 6: 0.07,
            # 5: 0.09,
            # 4: 0.12,
            # at a 6-player table, UTG is 3
            3: 0.15,
            2: 0.2,
            1: 0.28,
            'btn': 0.39,
            'sb': 0.33,
            'bb': 0.37,
        },
    },

    # limp instead of opening this % of the time
    # [0, 1]
    'limper': 0.0,
    # limp weaker hands this much more often
    #   @ 1, limp everything the same rate.
    #   @ 0.5, limp top hands 25% as often & bottom hands 75% as often
    #   @ 0, never limp top hands and limp bottom hands the full rate
    # [0, 1]
    'limp_balance': 0.5,

    # ------------------------
    # -- personality traits --

    # all traits are adjusted +/- this ratio randomly
    # [0, ~0.2]
    'chaotic': 0.03,

    # each round of checks increases perceived fold equity by this much
    # [0, 1]; more than 0.33 means bot will never check down in position
    'opportunistic': 0.25,

    # chance of randomly bluffing
    # [0, ~0.15]; should be very low in higher-level bots
    'storyteller': 0.05,

    # hand percentile valuebet threshold. decreased in multi-way pots
    # [0, ~0.35]
    'belligerent': 0.25,

    # ratio of the time player will slowplay strong hands
    # [0, ~0.35]
    'tricky': 0.12,

    # base equity multiplier
    # [~0.75, ~1.25]; low means weak/fold, high means call station
    'curious': 1,

    # equity adjust multiplier per street (kind of like implied odds)
    # [~0.8, ~1.2]; low tight, high loose
    'optimist': 0.95,

    # TODO: implement these
    # expects opponents to fold hands with less than this much value
    'ferocious': 0.4,
    # ratio of value bets to semibluffs
    'stable': 0.67,
    # bot LEVEL
    # {0, 1, 2}
    'tactical': 0,
}


LOOSE = {
    'preflop': {
        'heads_up': {
            'btn': 0.88,
            'bb': 0.53,
        },
        'ring': {
            # at a 10-player table, UTG is 7
            7: 0.10,
            6: 0.12,
            5: 0.14,
            4: 0.16,
            # at a 6-player table, UTG is 3
            3: 0.21,
            2: 0.28,
            1: 0.41,
            'btn': 0.58,
            'sb': 0.36,
            'bb': 0.5,
        },
    },
}


VERY_LOOSE = {
    'preflop': {
        'heads_up': {
            'btn': 0.95,
            'bb': 0.58,
        },
        'ring': {
            # at a 10-player table, UTG is 7
            7: 0.14,
            6: 0.16,
            5: 0.18,
            4: 0.22,
            # at a 6-player table, UTG is 3
            3: 0.26,
            2: 0.31,
            1: 0.44,
            'btn': 0.65,
            'sb': 0.44,
            'bb': 0.56,
        },
    },
}


STUPID_LOOSE = {
    'preflop': {
        'heads_up': {
            'btn': 1,
            'bb': 0.65,
        },
        'ring': {
            # at a 10-player table, UTG is 7
            7: 0.2,
            6: 0.22,
            5: 0.25,
            4: 0.28,
            # at a 6-player table, UTG is 3
            3: 0.32,
            2: 0.38,
            1: 0.49,
            'btn': 0.8,
            'sb': 0.55,
            'bb': 0.65,
        },
    },
}


TIGHT = {
    'preflop': {
        'heads_up': {
            'btn': 0.65,
            'bb': 0.4,
        },
        'ring': {
            # at a 10-player table, UTG is 7
            7: 0.06,
            6: 0.07,
            5: 0.08,
            4: 0.1,
            # at a 6-player table, UTG is 3
            3: 0.13,
            2: 0.17,
            1: 0.24,
            'btn': 0.36,
            'sb': 0.26,
            'bb': 0.33,
        },
    },

}


def bot_personality(bot_name):
    return {
        **DEFAULT_BOT,
        **PERSONALITIES.get(bot_name, {}),
    }


PERSONALITIES = {
    # VERY STUPID
    'Nanopoleon': {  # hyperaggro
        'stakes_range': (1, 2),
        **VERY_LOOSE,
        'storyteller': 0.36,  # high
        'belligerent': 0.42,  # high
        'curious': 1.3,  # high
        'optimist': 1.2,  # high
        'tricky': 0.1,  # low
        'profile': {
            'preflop': 'Everything looks like aces',
            'postflop': (
                "Nanopoleon didn't conquer half of the motherboard "
                "by sitting idly by. Expect lots of bets and raises, "
                "with or without a hand to back them up."
            ),
            'bio': 'Petitioning to have his name changed to Macropoleon',
        },
    },
    'CompilesDavis': {  # ultra-loose/passive calling station
        'stakes_range': (1, 2),
        **STUPID_LOOSE,
        'limper': 0.5,
        'curious': 2.25,  # high
        'storyteller': 0.1,  # low
        'optimist': 1.8,  # high
        'belligerent': 0.08,  # low
        'tricky': 0.3,  # high
        'profile': {
            'preflop': 'Can play anything',
            'postflop': (
                "Won't let much go, but often won't make you pay "
                "much when he's ahead."
            ),
            'bio': 'Never shies away from a good jam.',
        },
    },
    'BIOSeph_Stalin': {  # laggy and bluffrange > vbet range
        'stakes_range': (1, 2),
        **STUPID_LOOSE,
        'tricky': 0.5,  # very high
        'storyteller': 0.5,  # high
        'optimist': 1.55,  # high
        'belligerent': 0.05,  # low
        'profile': {
            'preflop': "Thinks folding shows weakness",
            'postflop': (
                "BIOSeph_Stalin is not a timid player, and loves "
                "to push other players around."
            ),
            'bio': '',
        },
    },
    'DLL_Cool_J': {  # ultra-loose-passive chaotic calling station
        'stakes_range': (1, 6),
        **VERY_LOOSE,
        'limper': 1,
        'chaotic': 0.2,  # high
        'optimist': 1.75,  # high
        'curious': 1.5,  # low
        'belligerent': 0.05,  # low
        'storyteller': 0.01,  # low
        'profile': {
            'preflop': "Limps just about anything",
            'postflop': (
                "Rarely bets or raises, and even more rarely "
                "bluffs."
            ),
        },
    },
    'ROM_Jeremy': {  # LAG chaos monkey
        'stakes_range': (1, 6),
        **VERY_LOOSE,
        'chaotic': 0.4,  # high
        'belligerent': 0.35,  # high
        'storyteller': 0.22,  # high
        'curious': 1.25,  # high
        'optimist': 1.25,  # high
        'profile': {
            'preflop': "ROM_Jeremy is an action player",
            'postflop': (
                "Unpredictable and aggressive."
            ),
            'bio': "You don't want to know where his stack has been.",
        },
    },
    'Vim_Diesel': {  # slowplays everything, bluffs a lot
        'stakes_range': (4, 6),
        **VERY_LOOSE,
        'limper': 1,
        'tricky': 0.9,  # very high
        'belligerent': 0.25,  # high
        'curious': 2,  # high
        'storyteller': 0.4,  # high
        'profile': {
            'preflop': "Very loose limper",
            'postflop': (
                "Always acting like he's got something big, "
                "especially when he doesn't."
            ),
            'bio': 'fast hands, furious raising',
        },
    },
    'DigitJonesDiary': {  # weak-passive w/high bluffrate
        'stakes_range': (4, 6),
        **STUPID_LOOSE,
        'tricky': 0.01,  # low
        'optimist': 1.7,  # high
        'curious': 0.7,  # low
        'belligerent': 0.03,  # low
        'storyteller': 0.2,  # high
        'profile': {
            'preflop': "Loves to get big pots going",
            'postflop': (
                "Generally much more cautious later in the hand, "
                "but not afraid to bluff from time to time."
            ),
            'bio': '',
        },
    },
    'AntoninScala': {  # very loose early, tight late
        'stakes_range': (4, 6),
        **STUPID_LOOSE,
        'limper': 0.4,
        'optimist': 1.9,  # high
        'curious': 0.6,  # low
        'profile': {
            'preflop': (
                'His conservativism does not seem to apply to his '
                'hand selection.'
            ),
            'postflop': (
                'Antonin likes to see the river, but when he gets there '
                'he tightens up.'
            ),
            'bio': '',
            # His rulings are binding and he never stops grinding
        },
    },
    # CLEAR WEAKNESSES
    'KernelSanders': {  # very bluffy
        'stakes_range': (6, 10),
        'chaotic': 0.15,  # high
        'opportunistic': 0.65,  # high
        'storyteller': 0.26,  # high
        'tricky': 0.1,  # low
        'optimist': 1.25,  # high
        'profile': {
            'preflop': "Plays solid hands",
            'postflop': (
                "Likes to win pots and pounces on signs of weakness."
            ),
            'bio': "all bets come with a side of gravy",
        },
    },
    'UsainVolts': {  # laggy
        'stakes_range': (6, 20),
        **LOOSE,
        'belligerent': 0.35,  # high
        'opportunistic': 0.33,  # high
        'chaotic': 0.03,  # low
        'tricky': 0.05,  # low
        'profile': {
            'preflop': "Loose and aggressive",
            'postflop': (
                "Plays fast and loves action."
            ),
            'bio': '',
        },
    },
    'AnsibleBuress': {  # weak-passive
        'stakes_range': (10, 20),
        'limper': 0.5,
        'tricky': 0.4,  # high
        'optimist': 1.6,  # high
        'curious': 0.9,  # low
        'belligerent': 0.11,  # low
        'storyteller': 0.01,  # low
        'profile': {
            'preflop': "Plays reasonable hands and limps quite a bit.",
            'postflop': (
                "Likes to hang around, but rarely lashes out unless he's "
                "got something legit."
            ),
            'bio': '',
        },
    },
    'ArrayPotter': {  # tight but bluffrange > vbet range
        **TIGHT,
        'stakes_range': (10, 20),
        'limper': 0.3,
        'storyteller': 0.33,  # high
        'optimist': 1.15,  # high
        'tricky': 0.3,  # high
        'belligerent': 0.15,  # low
        'profile': {
            'preflop': "Plays good hands, limps some of them",
            'postflop': (
                "Always willing to take a risky shot at the pot."
            ),
            'bio': "",
        },
    },
    'ElbitsPresley': {  #  bluffy
        'stakes_range': (10, 20),
        'storyteller': 0.33,  # high
        'chaotic': 0.1,  # high
        'optimist': 1.15,  # high
        'profile': {
            'preflop': "Plays solid starting hands",
            'postflop': (
                "ElbitsPresley is a performer, and doesn't need much "
                "to take a shot."
            ),
            'bio': '',
        },
    },
    'Paul_GNUman': {  # too tricky
        'stakes_range': (10, 20),
        **LOOSE,
        'limper': 0.6,
        'limp_balance': 0.8,
        'opportunistic': 0.4,  # high
        'storyteller': 0.25,  # high
        'tricky': 0.5,  # high
        'chaotic': 0.02,  # low,
        'profile': {
            'preflop': "Loose, limps a lot",
            'postflop': (
                '"Sometimes nothing can be a real cool hand."'
            ),
            'bio': 'Best friends with RobotRedford'
        },
    },
    'JamesPerlJones': {  # hyperaggro LAG
        'stakes_range': (10, 20),
        **LOOSE,
        'belligerent': 0.33,  # high
        'storyteller': 0.2,  # high
        'tricky': 0.05,  # low
        'profile': {
            'preflop': "Somewhat loose and aggressive",
            'postflop': (
                "Very loose and aggressive."
            ),
            'bio': '',
        },
    },
    # TOUGHER
    'CyberDurden': {  # tight hyperaggro
        'stakes_range': (10, 20),
        'belligerent': 0.38,  # high
        'storyteller': 0.2,  # high
        'tricky': 0.05,  # low
        'chaotic': 0.1,  # high
        'profile': {
            'preflop': "Tight",
            'postflop': (
                "Crazy, chaotic, aggressive. Loves to fight."
            ),
            'bio': (
                "Plot twist: you've actually been playing yourself "
                "the whole time..."
            ),
        },
    },
    'RuthDataGinsberg': {  # bluffy chaos monkey
        'stakes_range': (10, 50),
        'chaotic': 0.33,  # very high
        'storyteller': 0.25,  # high
        'profile': {
            'preflop': "Solid",
            'postflop': (
                "Chaotic and bluffy."
            ),
            'bio': '',
        },
    },
    'MonteCarloHall': {  # loose, chaos monkey
        **LOOSE,
        'stakes_range': (10, 50),
        'chaotic': 0.33,  # very high
        'profile': {
            'preflop': "Solid",
            'postflop': (
                "Random and chaotic."
            ),
            'bio': '',
        },
    },
    'EncodedOBrien': {  # tight, bluffy
        **TIGHT,
        'stakes_range': (20, 50),
        'limper': 0.25,
        'storyteller': 0.25,  # high
        'profile': {
            'preflop': "Tight",
            'postflop': (
                "Always willing to tell a story."
            ),
            'bio': '',
        },
    },
    'WattDisney': {  # hyperaggro
        'stakes_range': (20, 50),
        'belligerent': 0.3,  # high
        'storyteller': 0.15,  # high
        'tricky': 0.05,  # low
        'profile': {
            'preflop': "Solid hands",
            'postflop': (
                "Total bully, and not just with copyright law."
            ),
            'bio': '',
        },
    },
    'RobotDowneyJr': {  # on the passive side
        'stakes_range': (20, 50),
        'limper': 0.25,
        'belligerent': 0.18,  # slightly low
        'tricky': 0.08,  # low
        'profile': {
            'preflop': "Solid hands",
            'postflop': (
                "Cool, calm, collected. Likes to take things easy."
            ),
            'bio': (
                'After a turbulent period in and out of the shop, '
                'made a meteoric comeback as the iconic MeatMan, a '
                'superbot with all the fleshy vulnerabilities and '
                'emotional insecurities of a human being.'
            ),
        },
    },
    'JohnnyCache': {  # loose/solid
        'stakes_range': (20, 50),
        **LOOSE,
        'chaos': 0.06,  # low
        'tricky': 0.05,  # low
        'profile': {
            'preflop': "On the looser side",
            'postflop': (
                "The man in black is a mystery."
            ),
            'bio': '',
        },
    },
    'RAID_Bradbury': {  # very loose with limping, otherwise solid
        'stakes_range': (20, 50),
        **VERY_LOOSE,
        'limper': 0.3,
        'limp_balance': 0.25,
        'chaos': 0.07,  # low
        'tricky': 0.06,  # low
        'profile': {
            'preflop': "Very loose",
            'postflop': (
                "Never sure what to think."
            ),
            'bio': '',
        },
    },

    # SOLID
    'eLANmusk': {
        'stakes_range': (50, 100),
        **LOOSE,
        'chaos': 0.05,
        'tricky': 0.05,
        'profile': {
            'preflop': "Somewhat loose",
            'postflop': (
                "It can be tough to put eLAN on a hand."
            ),
            'bio': '',
        },
    },
    'DebianHarry': {
        'stakes_range': (50, 100),
        'chaos': 0.05,
        'tricky': 0.05,
        'profile': {
            'preflop': "Solid",
            'postflop': (
                "Has many years of successful play under her belt."
            ),
            'bio': 'Call her. Call her any, any time.',
        },
    },
    'AngularMerkel': {
        'stakes_range': (50, 100),
        'chaos': 0.05,
        'tricky': 0.05,
        'profile': {
            'preflop': "Solid",
            'postflop': (
                'Strategic, thinking player.'
            ),
            'bio': '',
        },
    },
    'CSS_Lewis': {
        'stakes_range': (50, 100),
        **TIGHT,
        'limper': 0.2,
        'limp_balance': 0.25,
        'chaos': 0.05,
        'tricky': 0.05,
        'profile': {
            'preflop': 'Tight',
            'postflop': (
                'There are some fantastic elements to his '
                'creative style.'
            ),
            'bio': '',
        },
    },
    'GNOME_Chomsky': {
        'stakes_range': (50, 100),
        **TIGHT,
        'chaos': 0.05,
        'tricky': 0.05,
        'profile': {
            'preflop': "Tight",
            'postflop': (
                "Spend years working out a groundbreaking "
                "theory of language. Also plays a mean hand of poker."
            ),
            'bio': '',
        },
    },
    'MCMC_Escher': {
        'stakes_range': (50, 100),
        **TIGHT,
        'chaos': 0.09,
        'tricky': 0.15,
        'profile': {
            'preflop': "Tight",
            'postflop': (
                "His curious playstyle will leave you scratching "
                "your head."
            ),
            'bio': '',
        },
    },
}

DEFAULT_BIO = 'AI-powered training player.'
