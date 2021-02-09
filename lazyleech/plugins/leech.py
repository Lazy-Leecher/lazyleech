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
import time
import html
import asyncio
import tempfile
from urllib.parse import urlparse, urlunparse, unquote as urldecode
from pyrogram import Client, filters
from pyrogram.parser import html as pyrogram_html
from .. import ADMIN_CHATS, ALL_CHATS, PROGRESS_UPDATE_DELAY, session, help_dict, LEECH_TIMEOUT, MAGNET_TIMEOUT, SendAsZipFlag, ForceDocumentFlag
from ..utils.aria2 import aria2_add_torrent, aria2_tell_status, aria2_remove, aria2_add_magnet, Aria2Error, aria2_tell_active, is_gid_owner, aria2_add_directdl
from ..utils.misc import format_bytes, get_file_mimetype, return_progress_string, calculate_eta, allow_admin_cancel
from ..utils.upload_worker import upload_queue, upload_statuses, progress_callback_data, upload_waits, stop_uploads

@Client.on_message(filters.command(['torrent', 'ziptorrent', 'filetorrent']) & filters.chat(ALL_CHATS))
async def torrent_cmd(client, message):
    text = (message.text or message.caption).split(None, 1)
    command = text.pop(0).lower()
    if 'zip' in command:
        flags = (SendAsZipFlag,)
    elif 'file' in command:
        flags = (ForceDocumentFlag,)
    else:
        flags = ()
    link = None
    reply = message.reply_to_message
    document = message.document
    if document:
        if document.file_size < 1048576 and document.file_name.endswith('.torrent') and (not document.mime_type or document.mime_type == 'application/x-bittorrent'):
            os.makedirs(str(message.from_user.id), exist_ok=True)
            fd, link = tempfile.mkstemp(dir=str(message.from_user.id), suffix='.torrent')
            os.fdopen(fd).close()
            await message.download(link)
            mimetype = await get_file_mimetype(link)
            if mimetype != 'application/x-bittorrent':
                os.remove(link)
                link = None
    if not link:
        if text:
            link = text[0].strip()
        elif not getattr(reply, 'empty', True):
            document = reply.document
            link = reply.text
            if document:
                if document.file_size < 1048576 and document.file_name.endswith('.torrent') and (not document.mime_type or document.mime_type == 'application/x-bittorrent'):
                    os.makedirs(str(message.from_user.id), exist_ok=True)
                    fd, link = tempfile.mkstemp(dir=str(message.from_user.id), suffix='.torrent')
                    os.fdopen(fd).close()
                    await reply.download(link)
                    mimetype = await get_file_mimetype(link)
                    if mimetype != 'application/x-bittorrent':
                        os.remove(link)
                        link = reply.text or reply.caption
    if not link:
        await message.reply_text('''Usage:
- /torrent <i>&lt;Torrent URL or File&gt;</i>
- /torrent <i>(as reply to a Torrent URL or file)</i>

- /ziptorrent <i>&lt;Torrent URL or File&gt;</i>
- /ziptorrent <i>(as reply to a Torrent URL or File)</i>

- /filetorrent <i>&lt;Torrent URL or File&gt;</i> - Sends videos as files
- /filetorrent <i>(as reply to a Torrent URL or file)</i> - Sends videos as files''')
        return
    await initiate_torrent(client, message, link, flags)
    await message.stop_propagation()

async def initiate_torrent(client, message, link, flags):
    user_id = message.from_user.id
    reply = await message.reply_text('Adding torrent...')
    try:
        gid = await aria2_add_torrent(session, user_id, link, LEECH_TIMEOUT)
    except Aria2Error as ex:
        await asyncio.gather(message.reply_text(f'Aria2 Error Occured!\n{ex.error_code}: {html.escape(ex.error_message)}'), reply.delete())
        return
    finally:
        if os.path.isfile(link):
            os.remove(link)
    await handle_leech(client, message, gid, reply, user_id, flags)

@Client.on_message(filters.command(['magnet', 'zipmagnet', 'filemagnet']) & filters.chat(ALL_CHATS))
async def magnet_cmd(client, message):
    text = (message.text or message.caption).split(None, 1)
    command = text.pop(0).lower()
    if 'zip' in command:
        flags = (SendAsZipFlag,)
    elif 'file' in command:
        flags = (ForceDocumentFlag,)
    else:
        flags = ()
    link = None
    reply = message.reply_to_message
    if text:
        link = text[0].strip()
    elif not getattr(reply, 'empty', True):
        link = reply.text or reply.caption
    if not link:
        await message.reply_text('''Usage:
- /magnet <i>&lt;Magnet URL&gt;</i>
- /magnet <i>(as reply to a Magnet URL)</i>

- /zipmagnet <i>&lt;Magnet URL&gt;</i>
- /zipmagnet <i>(as reply to a Magnet URL)</i>

- /filemagnet <i>&lt;Magnet URL&gt;</i> - Sends videos as files
- /filemagnet <i>(as reply to a Magnet URL)</i> - Sends videos as files''')
        return
    await initiate_magnet(client, message, link, flags)

async def initiate_magnet(client, message, link, flags):
    user_id = message.from_user.id
    reply = await message.reply_text('Adding magnet...')
    try:
        gid = await asyncio.wait_for(aria2_add_magnet(session, user_id, link, LEECH_TIMEOUT), MAGNET_TIMEOUT)
    except Aria2Error as ex:
        await asyncio.gather(message.reply_text(f'Aria2 Error Occured!\n{ex.error_code}: {html.escape(ex.error_message)}'), reply.delete())
    except asyncio.TimeoutError:
        await asyncio.gather(message.reply_text('Magnet timed out'), reply.delete())
    else:
        await handle_leech(client, message, gid, reply, user_id, flags)

@Client.on_message(filters.command(['directdl', 'direct', 'zipdirectdl', 'zipdirect', 'filedirectdl', 'filedirect']) & filters.chat(ALL_CHATS))
async def directdl_cmd(client, message):
    text = message.text.split(None, 1)
    command = text.pop(0).lower()
    if 'zip' in command:
        flags = (SendAsZipFlag,)
    elif 'file' in command:
        flags = (ForceDocumentFlag,)
    else:
        flags = ()
    link = filename = None
    reply = message.reply_to_message
    if text:
        link = text[0].strip()
    elif not getattr(reply, 'empty', True):
        link = reply.text
    if not link:
        await message.reply_text('''Usage:
- /directdl <i>&lt;Direct URL&gt; | optional custom file name</i>
- /directdl <i>(as reply to a Direct URL) | optional custom file name</i>
- /direct <i>&lt;Direct URL&gt; | optional custom file name</i>
- /direct <i>(as reply to a Direct URL) | optional custom file name</i>

- /zipdirectdl <i>&lt;Direct URL&gt; | optional custom file name</i>
- /zipdirectdl <i>(as reply to a Direct URL) | optional custom file name</i>
- /zipdirect <i>&lt;Direct URL&gt; | optional custom file name</i>
- /zipdirect <i>(as reply to a Direct URL) | optional custom file name</i>

- /filedirectdl <i>&lt;Direct URL&gt; | optional custom file name</i> - Sends videos as files
- /filedirectdl <i>(as reply to a Direct URL) | optional custom file name</i> - Sends videos as files
- /filedirect <i>&lt;Direct URL&gt; | optional custom file name</i> - Sends videos as files
- /filedirect <i>(as reply to a Direct URL) | optional custom file name</i> - Sends videos as files''')
        return
    split = link.split('|', 1)
    if len(split) > 1:
        filename = os.path.basename(split[1].strip())
        link = split[0].strip()
    parsed = list(urlparse(link, 'https'))
    if parsed[0] == 'magnet':
        if SendAsZipFlag in flags:
            prefix = 'zip'
        elif ForceDocumentFlag in flags:
            prefix = 'file'
        else:
            prefix = ''
        await message.reply_text(f'Use /{prefix}magnet instead')
        return
    if not parsed[0]:
        parsed[0] = 'https'
    if parsed[0] not in ('http', 'https'):
        await message.reply_text('Invalid scheme')
        return
    link = urlunparse(parsed)
    await initiate_directdl(client, message, link, filename, flags)

async def initiate_directdl(client, message, link, filename, flags):
    user_id = message.from_user.id
    reply = await message.reply_text('Adding url...')
    try:
        gid = await asyncio.wait_for(aria2_add_directdl(session, user_id, link, filename, LEECH_TIMEOUT), MAGNET_TIMEOUT)
    except Aria2Error as ex:
        await asyncio.gather(message.reply_text(f'Aria2 Error Occured!\n{ex.error_code}: {html.escape(ex.error_message)}'), reply.delete())
    except asyncio.TimeoutError:
        await asyncio.gather(message.reply_text('Connection timed out'), reply.delete())
    else:
        await handle_leech(client, message, gid, reply, user_id, flags)

leech_statuses = dict()
async def handle_leech(client, message, gid, reply, user_id, flags):
    prevtext = None
    torrent_info = await aria2_tell_status(session, gid)
    last_edit = 0
    start_time = time.time()
    message_identifier = (reply.chat.id, reply.message_id)
    leech_statuses[message_identifier] = gid
    download_speed = None
    while torrent_info['status'] in ('active', 'waiting', 'paused'):
        if torrent_info.get('seeder') == 'true':
            break
        status = torrent_info['status'].capitalize()
        total_length = int(torrent_info['totalLength'])
        completed_length = int(torrent_info['completedLength'])
        download_speed = format_bytes(torrent_info['downloadSpeed']) + '/s'
        if total_length:
            formatted_total_length = format_bytes(total_length)
        else:
            formatted_total_length = 'Unknown'
        formatted_completed_length = format_bytes(completed_length)
        seeders = torrent_info.get('numSeeders')
        peers = torrent_info.get('connections')
        if torrent_info.get('bittorrent'):
            tor_name = torrent_info['bittorrent']['info']['name']
        else:
            tor_name = os.path.basename(torrent_info['files'][0]['path'])
            if not tor_name:
                tor_name = urldecode(os.path.basename(urlparse(torrent_info['files'][0]['uris'][0]['uri']).path))
        text = f'''{html.escape(tor_name)}
<code>{html.escape(return_progress_string(completed_length, total_length))}</code>

<b>GID:</b> <code>{gid}</code>
<b>Status:</b> {status}
<b>Total Size:</b> {formatted_total_length}
<b>Downloaded Size:</b> {formatted_completed_length}
<b>Download Speed:</b> {download_speed}
<b>ETA:</b> {calculate_eta(completed_length, total_length, start_time)}'''
        if seeders is not None:
            text += f'\n<b>Seeders:</b> {seeders}'
        if peers is not None:
            text += f'\n<b>{"Peers" if seeders is not None else "Connections"}:</b> {peers}'
        if (time.time() - last_edit) > PROGRESS_UPDATE_DELAY and text != prevtext:
            await reply.edit_text(text)
            prevtext = text
            last_edit = time.time()
        torrent_info = await aria2_tell_status(session, gid)
    if torrent_info['status'] == 'error':
        error_code = torrent_info['errorCode']
        error_message = torrent_info['errorMessage']
        text = f'Aria2 Error Occured!\n{error_code}: {html.escape(error_message)}'
        if error_code == '7' and not error_message and torrent_info['downloadSpeed'] == '0':
            text += '\n\nThis error may have been caused due to the torrent being too slow'
        await asyncio.gather(
            message.reply_text(text),
            reply.delete()
        )
    elif torrent_info['status'] == 'removed':
        await asyncio.gather(
            message.reply_text('Your download has been manually cancelled.'),
            reply.delete()
        )
    else:
        leech_statuses.pop(message_identifier)
        task = None
        if upload_queue._unfinished_tasks:
            task = asyncio.create_task(reply.edit_text('Download successful, waiting for queue...'))
        upload_queue.put_nowait((client, message, reply, torrent_info, user_id, flags))
        try:
            await aria2_remove(session, gid)
        except Aria2Error as ex:
            if not (ex.error_code == 1 and ex.error_message == f'Active Download not found for GID#{gid}'):
                raise
        finally:
            if task:
                await task

@Client.on_message(filters.command('list') & filters.chat(ALL_CHATS))
async def list_leeches(client, message):
    user_id = message.from_user.id
    text = ''
    quote = None
    parser = pyrogram_html.HTML(client)
    for i in await aria2_tell_active(session):
        if i.get('bittorrent'):
            info = i['bittorrent'].get('info')
            if not info:
                continue
            tor_name = info['name']
        else:
            tor_name = os.path.basename(i['files'][0]['path'])
            if not tor_name:
                tor_name = urldecode(os.path.basename(urlparse(i['files'][0]['uris'][0]['uri']).path))
        a = f'''<b>{html.escape(tor_name)}</b>
<code>{i['gid']}</code>\n\n'''
        futtext = text + a
        if len((await parser.parse(futtext))['message']) > 4096:
            await message.reply_text(text, quote=quote)
            quote = False
            futtext = a
        text = futtext
    if not text:
        text = 'No leeches found.'
    await message.reply_text(text, quote=quote)

@Client.on_message(filters.command('cancel') & filters.chat(ALL_CHATS))
async def cancel_leech(client, message):
    user_id = message.from_user.id
    gid = None
    text = message.text.split(' ', 1)
    text.pop(0)
    reply = message.reply_to_message
    if text:
        gid = text[0].strip()
    elif not getattr(reply, 'empty', True):
        reply_identifier = (reply.chat.id, reply.message_id)
        task = upload_statuses.get(reply_identifier)
        if task:
            task, starter_id = task
            if user_id != starter_id and not await allow_admin_cancel(message.chat.id, user_id):
                await message.reply_text('You did not start this leech.')
            else:
                task.cancel()
            return
        result = progress_callback_data.get(reply_identifier)
        if result:
            if user_id != result[3] and not await allow_admin_cancel(message.chat.id, user_id):
                await message.reply_text('You did not start this leech.')
            else:
                stop_uploads.add(reply_identifier)
                await message.reply_text('Cancelled!')
            return
        starter_id = upload_waits.get(reply_identifier)
        if starter_id:
            if user_id != starter_id[0] and not await allow_admin_cancel(message.chat.id, user_id):
                await message.reply_text('You did not start this leech.')
            else:
                stop_uploads.add(reply_identifier)
                await message.reply_text('Cancelled!')
            return
        gid = leech_statuses.get(reply_identifier)
    if not gid:
        await message.reply_text('''Usage:
/cancel <i>&lt;GID&gt;</i>
/cancel <i>(as reply to status message)</i>''')
        return
    if not is_gid_owner(user_id, gid) and not await allow_admin_cancel(message.chat.id, user_id):
        await message.reply_text('You did not start this leech.')
        return
    await aria2_remove(session, gid)

help_dict['leech'] = ('Leech',
'''/torrent <i>&lt;Torrent URL or File&gt;</i>
/torrent <i>(as reply to a Torrent URL or file)</i>

/ziptorrent <i>&lt;Torrent URL or File&gt;</i>
/ziptorrent <i>(as reply to a Torrent URL or File)</i>

/filetorrent <i>&lt;Torrent URL or File&gt;</i> - Sends videos as files
/filetorrent <i>(as reply to a Torrent URL or File)</i> - Sends videos as files

/magnet <i>&lt;Magnet URL&gt;</i>
/magnet <i>(as reply to a Magnet URL)</i>

/zipmagnet <i>&lt;Magnet URL&gt;</i>
/zipmagnet <i>(as reply to a Magnet URL)</i>

/filemagnet <i>&lt;Magnet URL&gt;</i> - Sends videos as files
/filemagnet <i>(as reply to a Magnet URL)</i> - Sends videos as files

/directdl <i>&lt;Direct URL&gt; | optional custom file name</i>
/directdl <i>(as reply to a Direct URL) | optional custom file name</i>
/direct <i>&lt;Direct URL&gt; | optional custom file name</i>
/direct <i>(as reply to a Direct URL) | optional custom file name</i>

/zipdirectdl <i>&lt;Direct URL&gt; | optional custom file name</i>
/zipdirectdl <i>(as reply to a Direct URL) | optional custom file name</i>
/zipdirect <i>&lt;Direct URL&gt; | optional custom file name</i>
/zipdirect <i>(as reply to a Direct URL) | optional custom file name</i>

/filedirectdl <i>&lt;Direct URL&gt; | optional custom file name</i> - Sends videos as files
/filedirectdl <i>(as reply to a Direct URL) | optional custom file name</i> - Sends videos as files
/filedirect <i>&lt;Direct URL&gt; | optional custom file name</i> - Sends videos as files
/filedirect <i>(as reply to a Direct URL) | optional custom file name</i> - Sends videos as files

/cancel <i>&lt;GID&gt;</i>
/cancel <i>(as reply to status message)</i>

/list - Lists all current leeches''')
