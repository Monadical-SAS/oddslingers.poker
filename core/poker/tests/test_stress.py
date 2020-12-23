# import random

# from multiprocessing import Pool, Array

# from poker.bots import get_robot_move
# from poker.tests.test_controller import FivePlayerTableTest
# from poker.controllers import controller_for_table


# def be_a_robot(robot_id, table_id, n_loops, arr):
#     successes = 0
#     for _ in n_loops:
#         table = PokerTable.objects.get(id=table_id)
#         contr = controller_for_table(table)
#         player = contr.accessor.next_to_act()

#         if player is not None:
#             action, kwargs = get_robot_move(contr.accessor, player, delay=False)
#             try:
#                 contr.dispatch(action, **kwargs)
#                 successes += 1
#             except Exception as e:
#                 print("bot.{} exception: {}".format(robot_id, e))

#     arr[robot_id] = successes

# class ConcurrencyStressTest(FivePlayerTableTest):
#     def setUp(self):
#         super(ConcurrencyStressTest, self).setUp()
#         pool = Pool(4)

#     def test_concurrency(self):
#         players_remain = True
#         while(players_remain):
#             success_arr = Array('arr', 0.0)
#             n_actions = 20
#             results = pool.map([(i, self.table.id, n_actions, success_arr)
#                                                         for i in range(4)])

#             table = PokerTable.objects.get(id=self.table.id)
#             contr = controller_for_table(table)
#             players_remain = contr.accessor.next_to_act() is not None

#             if players_remain:
#                 assert sum(success_arr[:]) == n_actions

#             assert 1400 == sum(p.stack + p.wagers for p in contr.accessor.players)

