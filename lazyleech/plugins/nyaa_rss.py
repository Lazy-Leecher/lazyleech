import asyncio
import requests, random, time, os, lxml
from pyrogram import Client, filters
from bs4 import BeautifulSoup
from .. import app, ALL_CHATS
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

url = 'https://nyaa.si/?page=rss&q=720p&c=0_0&f=0&u=Erai-raws'
PING_TIME = int(os.environ.get("PING_TIME", 900))


async def start():
    nyaa_id1 = ""
    iterCount = 1
    while True:
        print("--------------------")
        print("Iteration(s) : {}".format(iterCount))
        print("--------------------")
        print("Implementation of Random Requests...")
        randomSleep = random.randint(5,6)
        time.sleep(randomSleep)
        print("Request Sleep time : {}".format(randomSleep))
        r = requests.get(url)
        print("Nyaa.si URL Loaded...")
        soup = BeautifulSoup(r.content,features='xml')
        all_title = soup.findAll("title")
        all_download = soup.findAll("link")
        all_view = soup.findAll("guid",{"isPermaLink":"true"})
        all_hash = soup.findAll("nyaa:infoHash")
        all_date = soup.findAll("pubDate")
        all_size = soup.findAll("nyaa:size")
        all_category = soup.findAll("nyaa:category")
        print("Scrapping...")
        spec_title = all_title[1].text
        spec_download = all_download[2].text
        spec_view = all_view[0].text
        spec_date = all_date[0].text
        spec_size = all_size[0].text
        spec_category = all_category[0].text
        spec_hash = all_hash[0].text
        nyaa_id = nyaa_id1
        print("Finishing up...")
        print("End of Iteration : {}".format(iterCount))
        iterCount+=1
        print("Scrapped Data Loaded to Variables...")
        if (nyaa_id!=spec_view):
            nyaa_id = spec_view
            nyaa_id1 = nyaa_id
            print("Finishing up...")
            print("End of Iteration : {}".format(iterCount))
            iterCount+=1
            keyboard = [
                [
                    InlineKeyboardButton("More Info",url = str(spec_view)),
                    InlineKeyboardButton("Download\nTorrent",url = str(spec_download))
                ]
            ]
            reply_markup1 = InlineKeyboardMarkup(keyboard)
            for i in ALL_CHATS:
                await Client.send_message(app, int(i), "<b>Name : <pre>%s</pre></b>\n<b>Category :</b> <pre>%s</pre>\n<b>Size :</b> <pre>%s</pre>\n<b>Publish Date :</b> <pre>%s</pre>\n<b>Magnet Link :</b> <pre>magnet:?xt=urn:btih:%s</pre>"%(spec_title, spec_category, spec_size, spec_date.replace("-0000","GMT"),spec_hash), reply_markup = reply_markup1)
        await pinger()


@Client.on_message("test")
async def bruh(client: Client, message: Message):
    if ALL_CHATS != message.chat.id:
        pass
    else:
        await message.reply_text("Test Result : TRUE ")


async def pinger():
    await asyncio.sleep(PING_TIME)
    await start()
