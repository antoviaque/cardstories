#
# Copyright (C) 2011 Loic Dachary <loic@dachary.org>
#
# This software's license gives you freedom; you can copy, convey,
# propagate, redistribute and/or modify this program under the terms of
# the GNU Affero General Public License (AGPL) as published by the Free
# Software Foundation (FSF), either version 3 of the License, or (at your
# option) any later version of the AGPL published by the FSF.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program in a file in the toplevel directory called
# "AGPLv3".  If not, see <http://www.gnu.org/licenses/>.
#
import sys
import os
sys.path.insert(0, os.path.abspath("..")) # so that for M-x pdb works
import sqlite3
import time

from twisted.trial import unittest, runner, reporter
from twisted.internet import defer

from cardstories.game import CardstoriesGame
from cardstories.service import CardstoriesService
from cardstories.exceptions import CardstoriesWarning

from twisted.internet import base
base.DelayedCall.debug = True

class CardstoriesGameTest(unittest.TestCase):

    def setUp(self):
        self.database = 'test.sqlite'
        if os.path.exists(self.database):
            os.unlink(self.database)
        self.service = CardstoriesService({'db': self.database})
        self.service.startService()
        self.db = sqlite3.connect(self.database)
        self.game = CardstoriesGame(self.service)

    def tearDown(self):
        self.game.destroy()
        self.db.close()
        os.unlink(self.database)
        return self.service.stopService()

    @defer.inlineCallbacks
    def test01_create(self):
        #
        # create a game from scratch
        #
        card = 5
        sentence = u'SENTENCE \xe9'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id);
        c = self.db.cursor()
        c.execute("SELECT * FROM games")
        rows = c.fetchall()
        self.assertEquals(1, len(rows))
        self.assertEquals(game_id, rows[0][0])
        self.assertEquals(owner_id, rows[0][1])
        one_player = 1
        self.assertEquals(one_player, rows[0][2])
        self.assertEquals(sentence, rows[0][3])
        self.assertFalse(chr(card) in rows[0][4])
        self.assertEquals(chr(card), rows[0][5])
        c.execute("SELECT cards FROM player2game WHERE game_id = %d AND player_id = %d" % (game_id, owner_id))
        rows = c.fetchall()
        self.assertEquals(1, len(rows))
        self.assertEquals(chr(card), rows[0][0])
        self.assertEquals(self.game.get_players(), [owner_id])
        self.assertEquals(self.game.get_owner_id(), owner_id)
        #
        # load an existing game
        #
        game = CardstoriesGame(self.service, self.game.get_id())
        game.load(c)
        self.assertEquals(game.get_players(), [owner_id])
        self.assertEquals(self.game.get_owner_id(), owner_id)
        game.destroy()
        c.close()

    @defer.inlineCallbacks
    def test02_participate(self):
        card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id)
        #
        # assert what happens when a player participates
        #
        c = self.db.cursor()
        c.execute("SELECT LENGTH(cards) FROM games WHERE id = %d" % game_id)
        cards_length = c.fetchone()[0]
        player_id = 23
        self.assertEquals([owner_id], self.game.get_players())
        participation = yield self.game.participate(player_id)
        self.assertEquals([game_id], participation['game_id'])
        self.assertEquals('participate', participation['type'])
        self.assertEquals(player_id, participation['player_id'])
        self.assertEquals([owner_id, player_id], self.game.get_players())
        c.execute("SELECT LENGTH(cards) FROM games WHERE id = %d" % game_id)
        self.assertEquals(cards_length - self.game.CARDS_PER_PLAYER, c.fetchone()[0])
        c.execute("SELECT LENGTH(cards) FROM player2game WHERE game_id = %d AND player_id = %d" % (game_id, player_id))
        self.assertEquals(self.game.CARDS_PER_PLAYER, c.fetchone()[0])
        c.close()
        #
        # assert the difference for when an invited player participates
        #
        invited = 20
        yield self.game.invite([invited])
        self.assertEquals([owner_id, player_id], self.game.players)
        self.assertEquals([invited], self.game.invited)
        participation = yield self.game.participate(invited)
        self.assertEquals([game_id], participation['game_id'])
        self.assertEquals([owner_id, player_id, invited], self.game.players)
        self.assertEquals([], self.game.invited)
        self.assertEquals([owner_id, player_id, invited], self.game.get_players())
        #
        # assert exception is raised when game is full
        #
        player_id = 30
        while len(self.game.players) < self.game.NPLAYERS:
            yield self.game.participate(player_id)
            player_id += 1
        # The game is full, trying to add another player should raise an exception.
        raises_CardstoriesException = False
        error_code = None
        error_data = {}
        try:
            yield self.game.participate(player_id)
        except CardstoriesWarning as e:
            raises_CardstoriesException = True
            error_code = e.code
            error_data = e.data
        self.assertTrue(raises_CardstoriesException)
        self.assertEquals('GAME_FULL', error_code)
        self.assertEquals(self.game.NPLAYERS, error_data['max_players'])

    @defer.inlineCallbacks
    def test03_player2game(self):
        card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id)
        player_id = 23
        yield self.game.participate(player_id)
        player = yield self.game.player2game(player_id)
        self.assertEquals(self.game.CARDS_PER_PLAYER, len(player['cards']))
        self.assertEquals(None, player['vote'])
        self.assertEquals(u'n', player['win'])

    @defer.inlineCallbacks
    def test04_pick(self):
        card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id)
        player2card = {}
        for player_id in (16, 17):
            yield self.game.participate(player_id)
            player = yield self.game.player2game(player_id)
            player2card[player_id] = player['cards'][0]
            result = yield self.game.pick(player_id, player2card[player_id])
            self.assertEquals(result['type'], 'pick')
            self.assertEquals(result['player_id'], player_id)
            self.assertEquals(result['card'], player2card[player_id])
        
        c = self.db.cursor()
        for player_id in (16, 17):
            c.execute("SELECT picked FROM player2game WHERE game_id = %d AND player_id = %d" % (game_id, player_id))
            self.assertEquals(player2card[player_id], ord(c.fetchone()[0]))
        c.close()
            
    @defer.inlineCallbacks
    def test05_state_vote(self):
        card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id)
        cards = [card]
        pick_players = [ 16, 17 ]
        players = pick_players + [ 18 ]
        for player_id in players:
            yield self.game.participate(player_id)
        for player_id in pick_players:
            player = yield self.game.player2game(player_id)
            card = player['cards'][0]
            cards.append(card)
            yield self.game.pick(player_id, card)
        invited = 20
        yield self.game.invite([invited])
        self.assertEquals([owner_id] + players + [invited], self.game.get_players())
        result = yield self.game.voting(owner_id)
        self.assertEquals(result['type'], 'voting')
        self.assertEquals([], self.game.invited)
        self.assertEquals([owner_id] + pick_players, self.game.get_players())
        c = self.db.cursor()
        c.execute("SELECT board, state FROM games WHERE id = %d" % (game_id))
        row = c.fetchone()
        board = map(lambda c: ord(c), row[0])
        board.sort()
        cards.sort()
        self.assertEquals(board, cards)
        self.assertEquals(u'vote', row[1])
        c.close()

    @defer.inlineCallbacks
    def test06_vote(self):
        card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id)
        for player_id in (16, 17):
            yield self.game.participate(player_id)
            player = yield self.game.player2game(player_id)
            card = player['cards'][0]
            yield self.game.pick(player_id, card)

        yield self.game.voting(owner_id)
        
        c = self.db.cursor()
        for player_id in (owner_id, 16, 17):
            vote = 1
            result = yield self.game.vote(player_id, vote)
            self.assertEquals(result['type'], 'vote')
            self.assertEquals(result['player_id'], player_id)
            self.assertEquals(result['vote'], vote)
            c.execute("SELECT vote FROM player2game WHERE game_id = %d AND player_id = %d" % (game_id, player_id))
            self.assertEqual(chr(vote), c.fetchone()[0])
        c.close()
            
    @defer.inlineCallbacks
    def test07_complete(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        voting_players = [ 16, 17 ]
        players = voting_players + [ 18 ]
        for player_id in players:
            yield self.game.participate(player_id)
            player = yield self.game.player2game(player_id)
            card = player['cards'][0]
            yield self.game.pick(player_id, card)
        
        yield self.game.voting(owner_id)

        c = self.db.cursor()
        c.execute("SELECT board FROM games WHERE id = %d" % game_id)
        board = c.fetchone()[0]
        winner_id = 16
        yield self.game.vote(winner_id, winner_card)
        loser_id = 17
        yield self.game.vote(loser_id, 120)
        self.assertEquals(self.game.get_players(), [owner_id] + players)
        result = yield self.game.complete(owner_id)
        self.assertEquals(result['type'], 'complete')
        self.assertEquals(self.game.get_players(), [owner_id] + players)
        c.execute("SELECT win, vote FROM player2game WHERE game_id = %d AND player_id != %d" % (game_id, owner_id))
        self.assertEqual((u'y', chr(winner_card)), c.fetchone())
        self.assertEqual(u'n', c.fetchone()[0])
        self.assertEqual((u'n', None), c.fetchone())
        self.assertEqual(c.fetchone(), None)
        c.close()
            
    @defer.inlineCallbacks
    def test08_game(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        # move to invitation state
        player1 = 16
        card1 = 20
        player2 = 17
        card2 = 25
        player3 = 18
        player4 = 19
        invited = [player3, player4]
        for player_id in (player1, player2):
            result = yield self.game.participate(player_id)
            self.assertEquals([game_id], result['game_id'])
        yield self.game.invite(invited)

        # invitation state, visitor point of view
        self.game.modified = 444
        game_info, players_id_list = yield self.game.game(None)
        self.assertEquals({'board': None,
                           'cards': None,
                           'id': game_id,
                           'ready': False,
                           'countdown_finish': None,
                           'owner': False,
                           'owner_id': owner_id,
                           'players': [{'id': owner_id, 'vote': None, 'win': u'n', 'picked': '', 'cards': None},
                                       {'id': player1, 'vote': None, 'win': u'n', 'picked': None, 'cards': None},
                                       {'id': player2, 'vote': None, 'win': u'n', 'picked': None, 'cards': None}],
                           'self': None,
                           'sentence': u'SENTENCE',
                           'winner_card': None,
                           'state': u'invitation',
                           'invited': None,
                           'modified': self.game.modified}, game_info)
        self.assertEquals(players_id_list, [owner_id, player1, player2])

        # invitation state, owner point of view
        game_info, players_id_list = yield self.game.game(owner_id)
        self.assertEquals([winner_card], game_info['board'])
        self.assertTrue(winner_card not in game_info['cards'])
        self.assertEquals(self.game.NCARDS, len(game_info['cards']) + sum(map(lambda player: len(player['cards']), game_info['players'])))
        self.assertTrue(game_info['owner'])
        self.assertFalse(game_info['ready'])
        self.assertEquals(winner_card, game_info['winner_card'])
        self.assertEquals(game_id, game_info['id'])
        self.assertEquals(invited, game_info['invited'])
        self.assertNotEquals(id(invited), id(game_info['invited']))
        self.assertEquals(owner_id, game_info['owner_id'])
        self.assertEquals(owner_id, game_info['players'][0]['id'])
        self.assertEquals(1, len(game_info['players'][0]['cards']))
        self.assertEquals(winner_card, game_info['players'][0]['picked'])
        self.assertEquals(player1, game_info['players'][1]['id'])
        self.assertEquals(None, game_info['players'][1]['picked'])
        self.assertEquals(self.game.CARDS_PER_PLAYER, len(game_info['players'][1]['cards']))
        self.assertEquals(player2, game_info['players'][2]['id'])
        self.assertEquals(None, game_info['players'][2]['picked'])
        self.assertEquals(self.game.CARDS_PER_PLAYER, len(game_info['players'][2]['cards']))
        self.assertEquals([winner_card, None, [winner_card]], game_info['self'])
        self.assertEquals(u'SENTENCE', game_info['sentence'])
        self.assertEquals(u'invitation', game_info['state'])
        self.assertEquals(players_id_list, [owner_id, player1, player2])

        # players vote
        result = yield self.game.pick(player1, card1)
        self.assertEquals([game_id], result['game_id'])
        result = yield self.game.pick(player2, card2)
        self.assertEquals([game_id], result['game_id'])

        # invitation state, owner point of view
        game_info, players_id_list = yield self.game.game(owner_id)
        self.assertTrue(game_info['ready'])
        # Assert modified is numeric; concrete type depends on architecture/implementation.
        self.assertTrue(isinstance(game_info['countdown_finish'], (int, long)))
        now_ms = time.time() * 1000
        self.assertTrue(game_info['countdown_finish'] > now_ms)
        self.assertEquals(players_id_list, [owner_id, player1, player2])

        # move to vote state
        result = yield self.game.voting(owner_id)
        self.assertEquals([game_id], result['game_id'])
        # vote state, owner point of view
        game_info, players_id_list = yield self.game.game(owner_id)
        game_info['board'].sort()
        self.assertEquals([winner_card, card1, card2], game_info['board'])
        self.assertTrue(winner_card not in game_info['cards'])
        self.assertEquals(self.game.NCARDS, len(game_info['cards']) + sum(map(lambda player: len(player['cards']), game_info['players'])))
        self.assertTrue(game_info['owner'])
        self.assertFalse(game_info['ready'])
        self.assertEquals(game_info['countdown_finish'], None)
        self.assertEquals(game_id, game_info['id'])
        self.assertEquals(owner_id, game_info['owner_id'])
        self.assertEquals(owner_id, game_info['players'][0]['id'])
        self.assertEquals(winner_card, game_info['players'][0]['picked'])
        self.assertEquals(1, len(game_info['players'][0]['cards']))
        self.assertEquals(player1, game_info['players'][1]['id'])
        self.assertEquals(card1, game_info['players'][1]['picked'])
        self.assertEquals(self.game.CARDS_PER_PLAYER, len(game_info['players'][1]['cards']))
        self.assertEquals(player2, game_info['players'][2]['id'])
        self.assertEquals(card2, game_info['players'][2]['picked'])
        self.assertEquals(self.game.CARDS_PER_PLAYER, len(game_info['players'][2]['cards']))
        self.assertEquals([winner_card, None, [winner_card]], game_info['self'])
        self.assertEquals(u'SENTENCE', game_info['sentence'])
        self.assertEquals(u'vote', game_info['state'])

        # every player vote
        result = yield self.game.vote(player1, card2)
        self.assertEquals([game_id], result['game_id'])
        result = yield self.game.vote(player2, card1)
        self.assertEquals([game_id], result['game_id'])
        # vote state, player point of view
        self.game.modified = 555
        game_info, players_id_list = yield self.game.game(player1)
        game_info['board'].sort()
        player1_cards = game_info['players'][1]['cards']
        countdown_finish = game_info['countdown_finish']
        self.assertTrue(isinstance(countdown_finish, (int, long)))
        now_ms = time.time() * 1000
        self.assertTrue(countdown_finish > now_ms)
        self.assertEquals({'board': [winner_card, card1, card2],
                           'cards': None,
                           'id': game_id,
                           'ready': True,
                           'countdown_finish': countdown_finish,
                           'owner': False,
                           'owner_id': owner_id,
                           'players': [{'id': owner_id, 'vote': None, 'win': u'n', 'picked': '', 'cards': None},
                                       {'id': player1, 'vote': '', 'win': u'n', 'picked': card1, 'cards': player1_cards},
                                       {'id': player2, 'vote': '', 'win': u'n', 'picked': '', 'cards': None}],
                           'self': [card1, card2, player1_cards],
                           'sentence': u'SENTENCE',
                           'winner_card': None,
                           'state': u'vote',
                           'invited': None,
                           'modified': self.game.modified}, game_info)
        self.assertEquals(players_id_list, [owner_id, player1, player2])
        # move to complete state

    @defer.inlineCallbacks
    def test08_game_player_order(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        # move to invitation state
        player1 = 16
        card1 = 20
        player2 = 17
        card2 = 25
        player3 = 18
        player4 = 19
        invited = [player3, player4]
        for player_id in (player2, player1):
            result = yield self.game.participate(player_id)
            self.assertEquals([game_id], result['game_id'])
        yield self.game.invite(invited)

        # invitation state, visitor point of view
        self.game.modified = 444
        game_info, players_id_list = yield self.game.game(None)
        self.assertEquals({'board': None,
                           'cards': None,
                           'id': game_id,
                           'ready': False,
                           'countdown_finish': None,
                           'owner': False,
                           'owner_id': owner_id,
                           'players': [{'id': owner_id, 'vote': None, 'win': u'n', 'picked': '', 'cards': None},
                                       {'id': player2, 'vote': None, 'win': u'n', 'picked': None, 'cards': None},
                                       {'id': player1, 'vote': None, 'win': u'n', 'picked': None, 'cards': None}],
                           'self': None,
                           'sentence': u'SENTENCE',
                           'winner_card': None,
                           'state': u'invitation',
                           'invited': None,
                           'modified': self.game.modified}, game_info)

    @defer.inlineCallbacks
    def test08_game_countdown_timeout(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        # move to invitation state
        player1 = 16
        card1 = 20
        player2 = 17
        card2 = 25
        for player_id in (player1, player2):
            result = yield self.game.participate(player_id)

        # change countdown duration prior to game ready
        yield self.game.set_countdown(1)

        # players vote
        result = yield self.game.pick(player1, card1)
        self.assertEquals([game_id], result['game_id'])
        result = yield self.game.pick(player2, card2)
        self.assertEquals([game_id], result['game_id'])

        game_info, players_id_list = yield self.game.game(owner_id)
        now_ms = time.time() * 1000
        self.assertTrue(now_ms < game_info['countdown_finish'] < now_ms + 1000)

        # move to vote state manually
        result = yield self.game.voting(owner_id)

        # every player vote
        result = yield self.game.vote(player1, card2)
        self.assertEquals([game_id], result['game_id'])
        result = yield self.game.vote(player2, card1)
        self.assertEquals([game_id], result['game_id'])

        # change countdown duration after game ready
        yield self.game.set_countdown(0.01)

        # auto move to complete state
        d = self.game.poll({'modified':[self.game.get_modified()]})
        def check(result):
            game_info = yield self.game.game(owner_id)
            self.assertEqual(game_info['state'], 'complete')
            self.assertEqual(game_info['countdown_finish'], None)
            self.assertEqual(result, None)
        d.addCallback(check)

    @defer.inlineCallbacks
    def test09_invitation(self):
        #
        # create a game and invite players
        #
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        invited = [20, 21]
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        self.assertEquals([owner_id], self.game.get_players())
        
        self.checked = False
        d = self.game.invite(invited)
        def check(result):
            self.checked = True
            self.assertNotEquals(id(invited), id(result['invited']))
            return result
        d.addCallback(check)
        result = yield d
        self.assertTrue(self.checked)
        self.assertEquals(result['type'], 'invite')
        self.assertEquals(result['invited'], invited)
        self.assertEquals([game_id], result['game_id'])
        self.assertEquals(invited, self.game.invited)
        self.assertEquals([owner_id] + invited, self.game.get_players())
        c = self.db.cursor()
        c.execute("SELECT * FROM invitations WHERE game_id = %d" % game_id)
        self.assertEquals(c.fetchall(), [(invited[0], game_id),
                                     (invited[1], game_id)])
        # inviting the same players twice is a noop
        result = yield self.game.invite(invited)
        self.assertEquals(result['type'], 'invite')
        self.assertEquals(result['invited'], [])
        #
        # load an existing game, invitations included
        #
        other_game = CardstoriesGame(self.service, self.game.get_id())
        other_game.load(c)
        self.assertEquals(other_game.get_players(), [owner_id] + invited)
        other_game.destroy()
        participation = yield self.game.participate(invited[0])
        self.assertEquals([game_id], result['game_id'])
        c.execute("SELECT * FROM invitations WHERE game_id = %d" % game_id)
        self.assertEquals(c.fetchall(), [(invited[1], game_id)])
        yield self.game.voting(owner_id)
        c.execute("SELECT * FROM invitations WHERE game_id = %d" % game_id)
        self.assertEquals(c.fetchall(), [])
        c.close()

    @defer.inlineCallbacks
    def test10_touch(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        result = yield self.game.touch()
        self.assertEquals([game_id], result['game_id'])
        self.assertEquals(self.game.modified, result['modified'][0])
        
    @defer.inlineCallbacks
    def test11_leave(self):
        card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id)
        cards = [card]
        players = [ 16, 17 ]
        for player_id in players:
            yield self.game.participate(player_id)
            player = yield self.game.player2game(player_id)
        modified = self.game.get_modified()
        self.assertTrue(players[0] in self.game.get_players())
        self.assertTrue(players[1] in self.game.get_players())
        result = yield self.game.leave_api({'player_id': players,
                                            'game_id': [self.game.get_id()] })
        self.assertTrue(self.game.get_modified() > modified)
        self.assertEqual(result['deleted'], 2)
        self.assertFalse(players[0] in self.game.get_players())
        self.assertFalse(players[1] in self.game.get_players())

    @defer.inlineCallbacks
    def test12_cancel(self):
        card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(card, sentence, owner_id)
        cards = [card]
        players = [ 16, 17 ]
        for player_id in players:
            yield self.game.participate(player_id)
        invited = 20
        yield self.game.invite([invited])
        self.assertEquals([owner_id] + players + [invited], self.game.get_players())

        game_info, players_game_info = yield self.game.game(owner_id)
        self.assertEquals(game_info['state'], u'invitation')
        self.assertEquals([ player['id'] for player in game_info['players']], [owner_id] + players)
        d = self.game.poll({'modified':[self.game.get_modified()]})
        def check(result):
            self.game.canceled = True
            self.assertEqual(result, None)
        d.addCallback(check)
        result = yield self.game.cancel()
        self.assertTrue(self.game.canceled)
        self.assertEquals(result, {})
        self.game.service = self.service
        game_info, players_game_info = yield self.game.game(owner_id)
        self.assertEquals(game_info['state'], u'canceled')
        self.assertEquals([ player['id'] for player in game_info['players']], [owner_id] + players)

    @defer.inlineCallbacks
    def test13_state_change(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        players = [ 16, 17 ]
        for player_id in players:
            yield self.game.participate(player_id)
            player = yield self.game.player2game(player_id)
            card = player['cards'][0]
            yield self.game.pick(player_id, card)
        
        result = yield self.game.state_change()
        self.assertEquals(result, CardstoriesGame.STATE_CHANGE_TO_VOTE)

        c = self.db.cursor()
        c.execute("SELECT board FROM games WHERE id = %d" % game_id)
        board = c.fetchone()[0]
        winner_id = 16
        yield self.game.vote(winner_id, winner_card)
        loser_id = 17
        yield self.game.vote(loser_id, 120)
        result = yield self.game.state_change()
        self.assertEquals(result, CardstoriesGame.STATE_CHANGE_TO_COMPLETE)
        c.execute("SELECT win FROM player2game WHERE game_id = %d AND player_id != %d" % (game_id, owner_id))
        self.assertEqual(u'y', c.fetchone()[0])
        self.assertEqual(u'n', c.fetchone()[0])
        self.assertEqual(c.fetchone(), None)
        c.close()

    @defer.inlineCallbacks
    def test14_state_change_cancel_invitation(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        cards = [winner_card]
        pick_players = [ 16 ]
        players = pick_players + [ 18 ]
        for player_id in players:
            yield self.game.participate(player_id)
        for player_id in pick_players:
            player = yield self.game.player2game(player_id)
            card = player['cards'][0]
            cards.append(card)
            yield self.game.pick(player_id, card)
        result = yield self.game.state_change()
        self.assertEquals(result, CardstoriesGame.STATE_CHANGE_CANCEL)

    @defer.inlineCallbacks
    def test15_state_change_cancel_voting(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        voting_players = [ 16 ]
        players = voting_players + [ 17, 18 ]
        for player_id in players:
            yield self.game.participate(player_id)
            player = yield self.game.player2game(player_id)
            card = player['cards'][0]
            yield self.game.pick(player_id, card)
        
        yield self.game.voting(owner_id)

        c = self.db.cursor()
        c.execute("SELECT board FROM games WHERE id = %d" % game_id)
        board = c.fetchone()[0]
        winner_id = 16
        yield self.game.vote(winner_id, winner_card)
        self.assertEquals(self.game.get_players(), [owner_id] + players)
        result = yield self.game.state_change()
        self.assertEquals(result, CardstoriesGame.STATE_CHANGE_CANCEL)

    @defer.inlineCallbacks
    def test16_timeout(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        self.game.settings['game-timeout'] = 0.01
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        d = self.game.poll({'modified': [self.game.get_modified()]})
        def check(result):
            self.assertEqual(self.game.get_players(), [owner_id])
            self.assertEqual(result, None)
            return result
        d.addCallback(check)
        result = yield d
        self.assertEqual(result, None)

    @defer.inlineCallbacks
    def test17_nonexistent_game(self):
        raises_CardstoriesException = False
        error_code = None
        try:
            self.game.id = 12332123
            yield self.game.game(None)
        except CardstoriesWarning as e:
            raises_CardstoriesException = True
            error_code = e.code
        self.assertTrue(raises_CardstoriesException)
        self.assertEqual('GAME_DOES_NOT_EXIST', error_code)

    @defer.inlineCallbacks
    def test18_complete_and_game_race(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        game_id = yield self.game.create(winner_card, sentence, owner_id)
        voting_players = [ 16, 17 ]
        players = voting_players + [ 18 ]
        for player_id in players:
            yield self.game.participate(player_id)
            player = yield self.game.player2game(player_id)
            card = player['cards'][0]
            yield self.game.pick(player_id, card)
        
        yield self.game.voting(owner_id)

        c = self.db.cursor()
        c.execute("SELECT board FROM games WHERE id = %d" % game_id)
        board = c.fetchone()[0]
        winner_id = 16
        yield self.game.vote(winner_id, winner_card)
        loser_id = 17
        yield self.game.vote(loser_id, 120)
        self.assertEquals(self.game.get_players(), [owner_id] + players)
        #
        # the game is about to be completed.
        # Create the race condition by:
        # a) calling game() and block it on the first runQuery
        # b) calling complete() and unblock the game() when it returns
        # c) resume game() which then needs to cope with the fact 
        #    that it is now using a game that has been destroyed
        #
        #
        # Replace the runQuery function by a wrapper that blocks the query.
        # It does it by creating a deferred that will run the original 
        # query when it fires. This deferred will need to be fired manually
        # by the enclosing test, when it needs it. This effectively creates
        # a condition that simulates a lag because the database is not
        # available.
        #
        original_runQuery = self.game.service.db.runQuery
        query_deferred = defer.Deferred()
        def fake_runQuery(*args):
            def f(result):
                r = original_runQuery(*args)
                return r
            query_deferred.addCallback(f)
            #
            # Now that the query has been wrapped in the deferred and the
            # calling function has been interrupted, restore the original
            # runQuery function so that the code keeps running as expected.
            #
            self.game.service.db.runQuery = original_runQuery
            return query_deferred
        # 
        # Because the runQuery is a fake, the deferred returned by self.game.game()
        # will actually be the deferred returned by the fake_runQuery function.
        # As a consequence the game.game() function will be blocked in the middle
        # of its execution, waiting for the deferred returned by fake_runQuery to 
        # be fired.
        #
        self.game.service.db.runQuery = fake_runQuery
        game_deferred = self.game.game(owner_id)
        #
        # The complete() function returns a deferred. The triggerGame() function is
        # added to the callback list of this deferred so that it resumes the interrupted
        # game.game() call by firing the deferred returned by fake_runQuery.
        # As a consequence, game.game() will complete its execution after the game has
        # been destroyed. It must cope with this because such concurrency will happen,
        # even if only rarely.
        #
        complete_deferred = self.game.complete(owner_id)
        def triggerGame(result):
            #
            # call destroy to reproduce the conditions of the service.py
            # complete() function. 
            #
            self.game.destroy()
            query_deferred.callback(True)
            return result
        complete_deferred.addCallback(triggerGame)
        result = yield complete_deferred
        game_result = yield game_deferred
        self.assertEquals(result['type'], 'complete')
        c.close()

    @defer.inlineCallbacks
    def test19_countdown(self):
        winner_card = 5
        sentence = 'SENTENCE'
        owner_id = 15
        yield self.game.create(winner_card, sentence, owner_id)
        self.assertEqual(self.game.get_countdown_duration(), self.game.DEFAULT_COUNTDOWN_DURATION)
        self.assertFalse(self.game.is_countdown_active())
        self.assertEqual(self.game.get_countdown_finish(), None)

        duration = 200
        self.game.set_countdown_duration(duration)
        self.assertEqual(self.game.get_countdown_duration(), duration)
        self.assertFalse(self.game.is_countdown_active())
        self.assertEqual(self.game.get_countdown_finish(), None)

        self.game.start_countdown()
        self.assertTrue(self.game.is_countdown_active())
        self.assertTrue(isinstance(self.game.get_countdown_finish(), (int, long)))
        now_ms = time.time() * 1000
        self.assertTrue(self.game.get_countdown_finish() > now_ms)

        self.game.clear_countdown()
        self.assertEqual(self.game.get_countdown_duration(), self.game.DEFAULT_COUNTDOWN_DURATION)
        self.assertFalse(self.game.is_countdown_active())
        self.assertEqual(self.game.get_countdown_finish(), None)

        self.game.set_countdown_duration(0.01)
        self.game.start_countdown()
        d = self.game.poll({'modified': [self.game.get_modified()]})
        def check(result):
            self.assertFalse(self.game.is_countdown_active())
            self.assertEqual(result, None)
        d.addCallback(check)

    @defer.inlineCallbacks
    def test20_pick_only_in_invitation_state(self):
        winner_card = 15
        sentence = 'SENTENCE'
        owner_id = 19
        player1_id = 53
        player2_id = 54
        player3_id = 55
        yield self.game.create(winner_card, sentence, owner_id)

        # Three players joining the game.
        for player_id in (player1_id, player2_id, player3_id):
            yield self.game.participate(player_id)

        # Two players pick cards.
        # They can do that while the game is in the 'invitation' state.
        yield self.game.pick(player1_id, 1)
        yield self.game.pick(player2_id, 2)

        # Move the game to the 'vote' state.
        yield self.game.voting(owner_id)

        # The third player can't pick a card anymore.
        raises_CardstoriesException = False
        error_code = None
        error_data = {}
        try:
            yield self.game.pick(player3_id, 3)
        except CardstoriesWarning as e:
            raises_CardstoriesException = True
            error_code = e.code
            error_data = e.data
        self.assertTrue(raises_CardstoriesException)
        self.assertEqual('WRONG_STATE_FOR_PICKING', error_code)
        self.assertEqual('vote', error_data['state'])

    @defer.inlineCallbacks
    def test21_vote_only_in_vote_state(self):
        winner_card = 25
        sentence = 'SENTENCE'
        owner_id = 12
        player1_id = 13
        player2_id = 14
        player3_id = 15
        yield self.game.create(winner_card, sentence, owner_id)

        # Three players joining the game.
        for player_id in (player1_id, player2_id, player3_id):
            yield self.game.participate(player_id)

        # The players pick cards.
        yield self.game.pick(player1_id, 1)
        yield self.game.pick(player2_id, 2)
        yield self.game.pick(player3_id, 3)

        # Try to vote now (not in the 'vote' state yet!).
        raises_CardstoriesException = False
        error_code = None
        error_data = {}
        try:
            yield self.game.vote(player1_id, 25)
        except CardstoriesWarning as e:
            raises_CardstoriesException = True
            error_code = e.code
            error_data = e.data
        self.assertTrue(raises_CardstoriesException)
        self.assertEqual('WRONG_STATE_FOR_VOTING', error_code)
        self.assertEqual('invitation', error_data['state'])

        # Move the game to the 'vote' state.
        yield self.game.voting(owner_id)

        # Two players vote.
        yield self.game.vote(player1_id, 25)
        yield self.game.vote(player2_id, 24)

        # Save reference to the db since the complete method will delete the
        # service object from the game.
        db = self.game.service.db

        # Move the game to the complete state and simulate a race condition
        # where the third player votes after the results have already been
        # calculated.
        yield self.game.complete(owner_id)

        # The third player can't vote anymore.
        # The exception here isn't the CardstoriesWarning, because the code
        # fails prior to that (since the game has been destroyed),
        # and the user error response is generated by the service, not the game.
        # So the only important thing to assert here is that trying to vote fails.
        raises_exception = False
        try:
            yield self.game.vote(player3_id, 25)
        except:
            raises_exception = True
        self.assertTrue(raises_exception)

        vote = yield db.runQuery("SELECT vote FROM player2game WHERE game_id = ? AND player_id = ?", [ self.game.get_id(), player3_id ])
        self.assertEquals(None, vote[0][0])

    @defer.inlineCallbacks
    def test22_game_is_destroy_upon_complete(self):
        winner_card = 25
        sentence = 'SENTENCE'
        owner_id = 12
        player1_id = 13
        player2_id = 14
        yield self.game.create(winner_card, sentence, owner_id)

        # The players join the game.
        yield self.game.participate(player1_id)
        yield self.game.participate(player2_id)
        # The players pick cards.
        yield self.game.pick(player1_id, 1)
        yield self.game.pick(player2_id, 2)
        # Move the game to the 'vote' state.
        yield self.game.voting(owner_id)
        # The players vote.
        yield self.game.vote(player1_id, 25)
        yield self.game.vote(player2_id, 24)

        # Mock out the game.destroy() method.
        orig_destroy = CardstoriesGame.destroy
        def fake_destroy(self):
            self.destroy_called = True
            orig_destroy(self)
        CardstoriesGame.destroy = fake_destroy

        # Complete the game, which should in turn call game.destroy().
        yield self.game.complete(owner_id)
        CardstoriesGame.destroy = orig_destroy
        self.assertTrue(self.game.destroy_called)
        # Clean up the mock.


def Run():
    loader = runner.TestLoader()
#    loader.methodPrefix = "test18_"
    suite = loader.suiteFactory()
    suite.addTest(loader.loadClass(CardstoriesGameTest))

    return runner.TrialRunner(
        reporter.VerboseTextReporter,
        tracebackFormat='default',
        ).run(suite)

if __name__ == '__main__':
    if Run().wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)

# Interpreted by emacs
# Local Variables:
# compile-command: "python-coverage -e ; PYTHONPATH=.. python-coverage -x test_game.py ; python-coverage -m -a -r ../cardstories/game.py"
# End:
