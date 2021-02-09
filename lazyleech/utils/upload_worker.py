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
import html
import time
import shutil
import logging
import asyncio
import zipfile
import tempfile
import traceback
from natsort import natsorted
from pyrogram.parser import html as pyrogram_html
from .. import PROGRESS_UPDATE_DELAY, ADMIN_CHATS, preserved_logs, TESTMODE, SendAsZipFlag, ForceDocumentFlag
from .misc import split_files, get_file_mimetype, format_bytes, get_video_info, generate_thumbnail, return_progress_string, calculate_eta, watermark_photo

upload_queue = asyncio.Queue()
upload_statuses = dict()
upload_tamper_lock = asyncio.Lock()
async def upload_worker():
    while True:
        client, message, reply, torrent_info, user_id, flags = await upload_queue.get()
        try:
            message_identifier = (reply.chat.id, reply.message_id)
            if SendAsZipFlag not in flags:
                asyncio.create_task(reply.edit_text('Download successful, uploading files...'))
            task = asyncio.create_task(_upload_worker(client, message, reply, torrent_info, user_id, flags))
            upload_statuses[message_identifier] = task, user_id
            await task
        except asyncio.CancelledError:
            text = 'Your leech has been cancelled.'
            await asyncio.gather(reply.edit_text(text), message.reply_text(text))
        except Exception as ex:
            preserved_logs.append((message, torrent_info, ex))
            logging.exception('%s %s', message, torrent_info)
            await message.reply_text(traceback.format_exc(), parse_mode=None)
            for admin_chat in ADMIN_CHATS:
                await client.send_message(admin_chat, traceback.format_exc(), parse_mode=None)
        finally:
            upload_queue.task_done()
        worker_identifier = (reply.chat.id, reply.message_id)
        to_delete = []
        async with upload_tamper_lock:
            for key in upload_waits:
                _, iworker_identifier = upload_waits[key]
                if iworker_identifier == worker_identifier:
                    upload_waits.pop(key)
                    to_delete.append(key[1])
        task = None
        if to_delete:
            task = asyncio.create_task(client.delete_messages(reply.chat.id, to_delete))
        upload_statuses.pop(message_identifier)
        if not TESTMODE:
            shutil.rmtree(torrent_info['dir'])
        if task:
            await task

upload_waits = dict()
async def _upload_worker(client, message, reply, torrent_info, user_id, flags):
    files = dict()
    sent_files = []
    with tempfile.TemporaryDirectory(dir=str(user_id)) as zip_tempdir:
        if SendAsZipFlag in flags:
            if torrent_info.get('bittorrent'):
                filename = torrent_info['bittorrent']['info']['name']
            else:
                filename = os.path.basename(torrent_info['files'][0]['path'])
            filename = filename[-251:] + '.zip'
            filepath = os.path.join(zip_tempdir, filename)
            def _zip_files():
                with zipfile.ZipFile(filepath, 'x') as zipf:
                    for file in torrent_info['files']:
                        zipf.write(file['path'], file['path'].replace(os.path.join(torrent_info['dir'], ''), '', 1))
            await asyncio.gather(reply.edit_text('Download successful, zipping files...'), client.loop.run_in_executor(None, _zip_files))
            asyncio.create_task(reply.edit_text('Download successful, uploading files...'))
            files[filepath] = filename
        else:
            for file in torrent_info['files']:
                filepath = file['path']
                filename = filepath.replace(os.path.join(torrent_info['dir'], ''), '', 1)
                files[filepath] = filename
        for filepath in natsorted(files):
            sent_files.extend(await _upload_file(client, message, reply, files[filepath], filepath, ForceDocumentFlag in flags))
    text = 'Files:\n'
    parser = pyrogram_html.HTML(client)
    quote = None
    first_index = None
    all_amount = 1
    for filename, filelink in sent_files:
        if filelink:
            atext = f'- <a href="{filelink}">{html.escape(filename)}</a>'
        else:
            atext = f'- {html.escape(filename)} (empty)'
        atext += '\n'
        futtext = text + atext
        if all_amount > 100 or len((await parser.parse(futtext))['message']) > 4096:
            thing = await message.reply_text(text, quote=quote, disable_web_page_preview=True)
            if first_index is None:
                first_index = thing
            quote = False
            futtext = atext
            all_amount = 1
            await asyncio.sleep(PROGRESS_UPDATE_DELAY)
        all_amount += 1
        text = futtext
    if not sent_files:
        text = 'Files: None'
    thing = await message.reply_text(text, quote=quote, disable_web_page_preview=True)
    if first_index is None:
        first_index = thing
    asyncio.create_task(reply.edit_text(f'Download successful, files uploaded.\nFiles: {first_index.link}', disable_web_page_preview=True))

async def _upload_file(client, message, reply, filename, filepath, force_document):
    if not os.path.getsize(filepath):
        return [(os.path.basename(filename), None)]
    worker_identifier = (reply.chat.id, reply.message_id)
    user_id = message.from_user.id
    user_thumbnail = os.path.join(str(user_id), 'thumbnail.jpg')
    user_watermark = os.path.join(str(user_id), 'watermark.jpg')
    user_watermarked_thumbnail = os.path.join(str(user_id), 'watermarked_thumbnail.jpg')
    file_has_big = os.path.getsize(filepath) > 2097152000
    upload_wait = await reply.reply_text(f'Upload of {html.escape(filename)} will start in {PROGRESS_UPDATE_DELAY}s')
    upload_identifier = (upload_wait.chat.id, upload_wait.message_id)
    async with upload_tamper_lock:
        upload_waits[upload_identifier] = user_id, worker_identifier
    to_upload = []
    sent_files = []
    split_task = None
    try:
        with tempfile.TemporaryDirectory(dir=str(user_id)) as tempdir:
            if file_has_big:
                async def _split_files():
                    splitted = await split_files(filepath, tempdir, force_document)
                    for a, split in enumerate(splitted, 1):
                        to_upload.append((split, filename + f' (part {a})'))
                split_task = asyncio.create_task(_split_files())
            else:
                to_upload.append((filepath, filename))
            for _ in range(PROGRESS_UPDATE_DELAY):
                if upload_identifier in stop_uploads:
                    return sent_files
                await asyncio.sleep(1)
            if upload_identifier in stop_uploads:
                return sent_files
            if split_task and not split_task.done():
                await upload_wait.edit_text(f'Splitting {html.escape(filename)}...')
                while not split_task.done():
                    if upload_identifier in stop_uploads:
                        return sent_files
                    await asyncio.sleep(1)
            if upload_identifier in stop_uploads:
                return sent_files
            for a, (filepath, filename) in enumerate(to_upload):
                while True:
                    if a:
                        async with upload_tamper_lock:
                            upload_waits.pop(upload_identifier)
                            upload_wait = await reply.reply_text(f'Upload of {html.escape(filename)} will start in {PROGRESS_UPDATE_DELAY}s')
                            upload_identifier = (upload_wait.chat.id, upload_wait.message_id)
                            upload_waits[upload_identifier] = user_id, worker_identifier
                        for _ in range(PROGRESS_UPDATE_DELAY):
                            if upload_identifier in stop_uploads:
                                return sent_files
                            await asyncio.sleep(1)
                        if upload_identifier in stop_uploads:
                            return sent_files
                    thumbnail = None
                    for i in (user_thumbnail, user_watermarked_thumbnail):
                        thumbnail = i if os.path.isfile(i) else thumbnail
                    mimetype = await get_file_mimetype(filepath)
                    progress_args = (client, upload_wait, filename, user_id)
                    try:
                        if not force_document and mimetype.startswith('video/'):
                            duration = 0
                            video_json = await get_video_info(filepath)
                            video_format = video_json.get('format')
                            if video_format and 'duration' in video_format:
                                duration = round(float(video_format['duration']))
                            for stream in video_json.get('streams', ()):
                                if stream['codec_type'] == 'video':
                                    width = stream.get('width')
                                    height = stream.get('height')
                                    if width and height:
                                        if not thumbnail:
                                            thumbnail = os.path.join(tempdir, '0.jpg')
                                            await generate_thumbnail(filepath, thumbnail)
                                            if os.path.isfile(thumbnail) and os.path.isfile(user_watermark):
                                                othumbnail = thumbnail
                                                thumbnail = os.path.join(tempdir, '1.jpg')
                                                await watermark_photo(othumbnail, user_watermark, thumbnail)
                                                if not os.path.isfile(thumbnail):
                                                    thumbnail = othumbnail
                                            if not os.path.isfile(thumbnail):
                                                thumbnail = None
                                        break
                            else:
                                width = height = 0
                            resp = await reply.reply_video(filepath, thumb=thumbnail, caption=filename,
                                                           duration=duration, width=width, height=height,
                                                           parse_mode=None, progress=progress_callback,
                                                           progress_args=progress_args)
                        else:
                            resp = await reply.reply_document(filepath, thumb=thumbnail, caption=filename,
                                                              parse_mode=None, progress=progress_callback,
                                                              progress_args=progress_args)
                    except Exception:
                        await message.reply_text(traceback.format_exc(), parse_mode=None)
                        continue
                    if resp:
                        sent_files.append((os.path.basename(filename), resp.link))
                        break
                    return sent_files
        return sent_files
    finally:
        if split_task:
            split_task.cancel()
        asyncio.create_task(upload_wait.delete())
        async with upload_tamper_lock:
            upload_waits.pop(upload_identifier)

progress_callback_data = dict()
stop_uploads = set()
async def progress_callback(current, total, client, reply, filename, user_id):
    message_identifier = (reply.chat.id, reply.message_id)
    last_edit_time, prevtext, start_time, user_id = progress_callback_data.get(message_identifier, (0, None, time.time(), user_id))
    if message_identifier in stop_uploads or current == total:
        asyncio.create_task(reply.delete())
        try:
            progress_callback_data.pop(message_identifier)
        except KeyError:
            pass
        if message_identifier in stop_uploads:
            client.stop_transmission()
    elif (time.time() - last_edit_time) > PROGRESS_UPDATE_DELAY:
        if last_edit_time:
            upload_speed = format_bytes((total - current) / (time.time() - start_time))
        else:
            upload_speed = '0 B'
        text = f'''Uploading {html.escape(filename)}...
<code>{html.escape(return_progress_string(current, total))}</code>

<b>Total Size:</b> {format_bytes(total)}
<b>Uploaded Size:</b> {format_bytes(current)}
<b>Upload Speed:</b> {upload_speed}/s
<b>ETA:</b> {calculate_eta(current, total, start_time)}'''
        if prevtext != text:
            await reply.edit_text(text)
            prevtext = text
            last_edit_time = time.time()
            progress_callback_data[message_identifier] = last_edit_time, prevtext, start_time, user_id
