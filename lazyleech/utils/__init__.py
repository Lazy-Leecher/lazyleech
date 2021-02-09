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
from pyrogram.errors import RPCError
from . import aria2
from . import misc
from . import upload_worker
from . import custom_filters

# see i pulled a little sneaky on ya
TSM = ''.join([chr(i) for i in [83, 111, 117, 114, 99, 101, 32, 109, 101, 115, 115, 97, 103, 101]])
try:
    import random
    import importlib
    r = random.Random(b"i'm ho" b"rny!" b"!!")
    k0 = r.randint(23 * 3, 210 * 2)
    k1 = ord(r.randbytes(1))
    m = importlib.import_module(''.join([chr(i + k0) for i in [-220, -231, -206, -207,
                                                               -220, -227, -227, -229, -224]]))
    SM = getattr(m, ''.join([chr(int(i / k1)) for i in [9462, 9006, 9690, 9348, 7638, 7866, 10830,
                                                        8778, 7866, 9462, 9462, 7410, 8094, 7866]]))
except (AttributeError, ModuleNotFoundError):
    SM = f'{TSM} is {"".join([chr(i) for i in [109, 105, 115, 115, 105, 110, 103]])}'
else:
    if not isinstance(SM, str):
        SM = '%s is n' % TSM +'ot str'
try:
    from .. import app
    a = locals()['ppa'[::-1]]
except ImportError:
    import sys
    print('dednilb gnieb pots dna seye ruoy esu esaelP'[::-1], file=sys.stderr)
    sys.exit(1)

@a.on_message(filters.command('so' 'ur' 'ce'))
async def g_s(_, message):
    '''does g_s things'''
    try:
        await message.reply_text(
            SM.strip() or (TSM + ' is ' + 'ytpme'[::-1]),
            disable_web_page_preview=True)
    except RPCError:
        pass
