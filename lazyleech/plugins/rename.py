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

import asyncio
import html
import math
import os
import re

from pyrogram import Client, filters

from .. import ALL_CHATS, help_dict, ForceDocumentFlag, SendAsZipFlag, PROGRESS_UPDATE_DELAY
from ..utils.upload_worker import _upload_file


@Client.on_message(filters.command(['rename', 'filerename']) & filters.chat(ALL_CHATS))
async def rename(client, message):
    text = message.command
    command = text.pop(0).lower()
    if 'file' in command:
        flags = (ForceDocumentFlag,)
    else:
        flags = ()
    name = message.text.split(None, 1)[1]
    available_media = ("audio", "document", "photo", "sticker", "animation", "video", "voice", "video_note")
    download_message = None
    for i in available_media:
        if getattr(message, i, None):
            download_message = message
            break
    else:
        reply = message.reply_to_message
        if not getattr(reply, 'empty', True):
            for i in available_media:
                if getattr(reply, i, None):
                    download_message = reply
                    break
    if download_message is None:
        await message.reply_text('Media required')
        return
    filepath = name
    msg = await message.reply_text('Downloading...')
    await download_message.download(filepath)
    await msg.edit_text("Uploading...")
    await asyncio.sleep(PROGRESS_UPDATE_DELAY)
    await _upload_file(client, message, msg, name, filepath, flags)
    await msg.edit_text("File renamed")
    os.remove(filepath)

help_dict['rename'] = ('Rename',
'''<b>Rename</b>
/rename <i>as reply to file or as a caption</i>
/filerename <i>as reply to file or as a caption</i>''')
