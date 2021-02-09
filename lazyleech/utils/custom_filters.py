# lazyleech - Telegram bot primarily to leech from torrents and upload to Telegram
# Copyright (c) 2021 lazyleech developers <theblankx protonmail com, meliodas_bot protonmail com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from pyrogram import filters

def callback_data(data):
    def func(flt, client, callback_query):
        return callback_query.data in flt.data

    data = data if isinstance(data, list) else [data]
    return filters.create(
        func,
        'CustomCallbackDataFilter',
        data=data
    )

def callback_chat(chats):
    def func(flt, client, callback_query):
        return callback_query.message.chat.id in flt.chats

    chats = chats if isinstance(chats, list) else [chats]
    return filters.create(
        func,
        'CustomCallbackChatsFilter',
        chats=chats
    )
