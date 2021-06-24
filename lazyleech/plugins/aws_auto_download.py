### if you wish to disable this just fork repo and delete this plugin/file
### if you want different uploader, just replace rsslink

import os
import asyncio
import requests
import re
from bs4 import BeautifulSoup as bs
from motor.motor_asyncio import AsyncIOMotorClient
from motor.core import AgnosticClient, AgnosticDatabase, AgnosticCollection
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, filters
from .. import app, ADMIN_CHATS, ForceDocumentFlag
from .leech import initiate_torrent

rsslink = "https://nyaa.si/?page=rss&q=-batch&c=0_0&f=0&u=AkihitoSubsWeeklies"

if os.environ.get('DB_URL'):
    DB_URL = os.environ.get('DB_URL')
    _MGCLIENT: AgnosticClient = AsyncIOMotorClient(DB_URL)
    _DATABASE: AgnosticDatabase = _MGCLIENT["ASWFeed"]
    def get_collection(name: str) -> AgnosticCollection:
        """ Create or Get Collection from your database """
        return _DATABASE[name]
    def _close_db() -> None:
        _MGCLIENT.close()
    
    A = get_collection('ASW_TITLE')
    
    async def rss_parser():
        da = bs(requests.get(rsslink).text, features="html.parser")
        if (await A.find_one())==None:
            await A.insert_one({'_id': str(da.find('item').find('title'))})
            return
        count_a = 0
        cr = []
        for i in da.findAll('item'):
            if (await A.find_one())['_id'] == str(i.find('title')):
                break
            cr.append([str(i.find('title')), (re.sub(r'<.*?>(.*)<.*?>', r'\1', str(i.find('guid')))).replace('view', 'download')+'.torrent'])
            count_a+=1
        if count_a!=0:
            await A.drop()
            await A.insert_one({'_id': str(da.find('item').find('title'))})
        for i in cr:
            for ii in ADMIN_CHATS:
                msg = await app.send_message(ii, f"New anime uploaded\n\n{i[0]}\n{i[1]}")
                flags = (ForceDocumentFlag,)
                await initiate_torrent(app, msg, i[1], flags)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(rss_parser, "interval", minutes=15)
    scheduler.start()
