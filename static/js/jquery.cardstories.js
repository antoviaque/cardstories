//
//     Copyright (C) 2011 Loic Dachary <loic@dachary.org>
//
//     This program is free software: you can redistribute it and/or modify
//     it under the terms of the GNU General Public License as published by
//     the Free Software Foundation, either version 3 of the License, or
//     (at your option) any later version.
//
//     This program is distributed in the hope that it will be useful,
//     but WITHOUT ANY WARRANTY; without even the implied warranty of
//     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//     GNU General Public License for more details.
//
//     You should have received a copy of the GNU General Public License
//     along with this program.  If not, see <http://www.gnu.org/licenses/>.
//
(function($) {

    $.cardstories = {
        url: "../resource",

        error: function(error) { alert(error); },

        xhr_error: function(xhr, status, error) {
	    $.cardstories.error(error);
        },

        setTimeout: function(cb, delay) { return window.setTimeout(cb, delay); },

        ajax: function(o) { return jQuery.ajax(o); },

	create: function(player_id, element) {
	    var $this = this;
	    $('input[name="card"]:nth(0)', element).attr('checked', 'checked');
            $('input[type=submit]', element).click(function() {
                var success = function(data, status) {
                    if('error' in data) {
                        $this.error(data.error);
                    } else {
                        $this.setTimeout(function() { $this.game(player_id, data.game_id, element); }, 30);
		    }
                };
                var sentence = encodeURIComponent($('input[name="sentence"]', element).val());
 		var card = $('input[name="card"]:checked', element).val();
                $this.ajax({
                    async: false,
                    timeout: 30000,
                    url: $this.url + '?action=create&owner_id=' + player_id + '&card='+ card,
                    type: 'POST',
                    data: 'sentence=' + sentence,
                    dataType: 'json',
                    global: false,
                    success: success,
		    error: $this.xhr_error
		});
	    });
	},

	invitation: function(player_id, game, element) {
	    if(game.owner) {
		this.invitation_owner(player_id, game, $('.cardstories_owner', element));
	    } else {
		if(game.self !== null && game.self !== undefined) {
		    this.invitation_pick(player_id, game, $('.cardstories_pick', element));
		} else {
		    this.invitation_participate(player_id, game, $('.cardstories_participate', element));
		}
	    }
	},

	invitation_owner: function(player_id, game, element) {
	    var $this = this;
	    $('a.cardstories_invite').attr('href', '?game_id=' + game.id);
	    $('a.cardstories_refresh').attr('href', '?player_id=' + player_id + '&game_id=' + game.id);
            var voting = $('.cardstories_voting', element);
	    voting.toggleClass('cardstories_ready', game.ready);
	    if(game.ready) {
		voting.click(function() {
		    $this.send(player_id, game.id, element, 'action=voting&owner_id=' + player_id + '&game_id=' + game.id);
		});
	    }
	},

	invitation_pick: function(player_id, game, element) {
	    var $this = this;
	    $('.cardstories_sentence', element).text(game.sentence);
            $('.cardstories_card', element).unbind('click').click(function() {
		var card = $(this).metadata().card;
		$this.send(player_id, game.id, element, 'action=pick&player_id=' + player_id + '&game_id=' + game.id + '&card=' + card);
	    });
	    var cards = game.self[2];
	    $('.cardstories_card', element).each(function(index) {
		$(this).attr('class', 'cardstories_card cardstories_card' + cards[index] + ' {card:' + cards[index] + '}');
	    });
	},

	invitation_participate: function(player_id, game, element) {
	    var $this = this;
	    $('.cardstories_sentence', element).text(game.sentence);
            $('input[type=submit]', element).click(function() {
		$this.send(player_id, game.id, element, 'action=participate&player_id=' + player_id + '&game_id=' + game.id);
	    });
	},

	vote: function(player_id, game, element) {
	    if(game.owner) {
		this.vote_owner(player_id, game, $('.cardstories_owner', element));
	    } else {
		if(game.self !== null && game.self !== undefined) {
		    this.vote_voter(player_id, game, $('.cardstories_voter', element));
		} else {
		    this.vote_viewer(player_id, game, $('.cardstories_participate', element));
		}
	    }

	},

	vote_voter: function(player_id, game, element) {
	    var $this = this;
	    $('.cardstories_sentence', element).text(game.sentence);
	    var cards = game.board;
	    var picked = game.self[0];
	    var voted = game.self[1];
	    $('.cardstories_card', element).each(function(index) {
		var c = 'cardstories_card cardstories_card' + cards[index] + ' {card:' + cards[index] + '}';
		if(picked == cards[index]) {
		    c += ' cardstories_picked';
		}
		if(voted && voted == cards[index]) {
		    c += ' cardstories_voted';
		}
		$(this).attr('class', c);
	    });
            $('.cardstories_card', element).not('.cardstories_picked').unbind('click').click(function() {
		var card = $(this).metadata().card;
		$this.send(player_id, game.id, element, 'action=vote&player_id=' + player_id + '&game_id=' + game.id + '&vote=' + card);
	    });
	},

	complete: function(player_id, game, element) {
	},

	send: function(player_id, game_id, element, query, data) {
	    var $this = this;
	    var root = $(element).parents('.cardstories_root');
            var success = function(data, status) {
		if('error' in data) {
                    $this.error(data.error);
		} else {
                    $this.setTimeout(function() { $this.game(player_id, game_id, root); }, 30);
		}
            };
	    var request = {
		async: false,
		timeout: 30000,
		url: $this.url + '?' + query,
		dataType: 'json',
		global: false,
		success: success,
		error: $this.xhr_error
	    };
	    if(data !== undefined) {
		request.type = 'POST';
		request.data = data;
	    } else {
		request.type = 'GET';
	    }
            $this.ajax(request);
	},

	game: function(player_id, game_id, element) {
	    var $this = this;
            var success = function(data, status) {
		if('error' in data) {
                    $this.error(data.error);
		} else {
		    $this[data.state](player_id, data, $('.cardstories_' + data.state, element));
		}
            };
            $this.ajax({
		async: false,
		timeout: 30000,
		url: $this.url + '?action=game&game_id=' + game_id + '&player_id=' + player_id,
		type: 'GET',
		dataType: 'json',
		global: false,
		success: success,
		error: $this.xhr_error
            });
	}
    };

    $.fn.cardstories = function(player_id, game_id) {
        return this.each(function() {
	    if(!$(this).hasClass('cardstories_root')) {
		$(this).addClass('cardstories_root');
	    }
	    if(game_id === undefined || game_id === '') {
		$.cardstories.create(player_id, $('.cardstories_create', this));
	    } else {
		$.cardstories.game(player_id, game_id, $(this));
	    }
            return this;
        });
    };

})(jQuery);
