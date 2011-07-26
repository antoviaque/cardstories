(function($) {

    $.cardstories_chat = {
        message_line_template: '<div class="cardstories_chat_message"><span>{player_id}:</span> {line}</div>',

        init: function(display, input) {
            var self = this;
            this.data('cardstories_chat', {display: display, input: input});
            input.placeholder();

            input.keydown(function(event) {
                if (event.which === 13) {
                    var line = input.val();
                    if ($.trim(line) && line !== input.attr('placeholder')) {
                        $.cardstories_chat.plugin_send.call(self, line);
                    }
                    input.val('');
                }
            });
        },

        // The assumption here is that the sentences have already been
        // HTML escaped to prevent from XSS attacks.
        plugin_chat: function(data) {
            var messages = data.messages;
            for (var i = 0, len = messages.length; i < len; i++) {
                var line = messages[i].sentence;
                var player_id = messages[i].player_id;
                var div = $.cardstories_chat.message_line_template.supplant({line: line, player_id: player_id});
                var display = this.data('cardstories_chat').display;
                display.append(div).scrollTop(display[0].scrollHeight);
            }
        },

        plugin_send: function(line) {
            throw('No implementation of the $.cardstories_chat.plugin_send function has been provided.')
        }
    };

    $.fn.cardstories_chat = function(method) {
        if ($.cardstories_chat[method]) {
            return $.cardstories_chat[method].apply(this, Array.prototype.slice.call(arguments, 1));
        } else if (!this.data('cardstories_chat')) {
            var display = this.find('.cardstories_chat_display');
            var input = this.find('.cardstories_chat_input');
            $.cardstories_chat.init.call(this, display, input);
        }

        return this;
    };

})(jQuery);