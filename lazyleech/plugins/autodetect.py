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

import os
import re
import time
import asyncio
import tempfile
from urllib.parse import urlsplit
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .. import ALL_CHATS, SendAsZipFlag, ForceDocumentFlag
from ..utils.misc import get_file_mimetype
from ..utils import custom_filters
from .leech import initiate_torrent, initiate_magnet

NYAA_REGEX = re.compile(r'^(?:https?://)?(?P<base>(?:www\.|sukebei\.)?nyaa\.si|nyaa\.squid\.workers\.dev)/(?:view|download)/(?P<sauce>\d+)(?:[\./]torrent)?$')
auto_detects = dict()
@Client.on_message(filters.chat(ALL_CHATS), group=1)
async def autodetect(client, message):
    text = message.text
    document = message.document
    link = None
    is_torrent = False
    if document:
        if document.file_size < 1048576 and document.file_name.endswith('.torrent') and (not document.mime_type or document.mime_type == 'application/x-bittorrent'):
            os.makedirs(str(message.from_user.id), exist_ok=True)
            fd, link = tempfile.mkstemp(dir=str(message.from_user.id), suffix='.torrent')
            os.fdopen(fd).close()
            await message.download(link)
            mimetype = await get_file_mimetype(link)
            is_torrent = True
            if mimetype != 'application/x-bittorrent':
                os.remove(link)
                link = None
                is_torrent = False
    if not link and text:
        match = NYAA_REGEX.match(text)
        if match:
            link = f'https://{match.group("base")}/download/{match.group("sauce")}.torrent'
            is_torrent = True
        else:
            splitted = urlsplit(text)
            if splitted.scheme == 'magnet' and splitted.query:
                link = text
    if link:
        reply = await message.reply_text(f'{"Torrent" if is_torrent else "Magnet"} detected. Select upload method', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('Individual Files', 'autodetect_individual'), InlineKeyboardButton('Zip', 'autodetect_zip'), InlineKeyboardButton('Force Document', 'autodetect_file')],
            [InlineKeyboardButton('Delete', 'autodetect_delete')]
        ]))
        auto_detects[(reply.chat.id, reply.message_id)] = link, message.from_user.id, (initiate_torrent if is_torrent else initiate_magnet)

answered = set()
answer_lock = asyncio.Lock()
@Client.on_callback_query(custom_filters.callback_data(['autodetect_individual', 'autodetect_zip', 'autodetect_file', 'autodetect_delete']) & custom_filters.callback_chat(ALL_CHATS))
async def autodetect_callback(client, callback_query):
    message = callback_query.message
    identifier = (message.chat.id, message.message_id)
    result = auto_detects.get(identifier)
    if not result:
        await callback_query.answer('I can\'t get your message, please try again.', show_alert=True, cache_time=3600)
        return
    link, user_id, init_func = result
    if callback_query.from_user.id != user_id:
        await callback_query.answer('...no', cache_time=3600)
        return
    async with answer_lock:
        if identifier in answered:
            await callback_query.answer('...no')
            return
        answered.add(identifier)
    asyncio.create_task(message.delete())
    data = callback_query.data
    start_leech = data in ('autodetect_individual', 'autodetect_zip', 'autodetect_file')
    if start_leech:
        if getattr(message.reply_to_message, 'empty', True):
            await callback_query.answer('Don\'t delete your message!', show_alert=True)
            return
        if data == 'autodetect_zip':
            flags = (SendAsZipFlag,)
        elif data == 'autodetect_file':
            flags = (ForceDocumentFlag,)
        else:
            flags = ()
        await asyncio.gather(callback_query.answer(), init_func(client, message.reply_to_message, link, flags))
