import asyncio
import socket
import aiohttp
from telethon import events
from config import COMMAND_PREFIX, PROXY_CHECK_LIMIT, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

PROXY_TIMEOUT = 10
GEOLOCATION_TIMEOUT = 3

class HTTPProxyChecker:
    def __init__(self):
        self.geo_service = {
            'name': 'ipinfo.io',
            'url': "https://ipinfo.io/{ip}/json",
            'parser': lambda data: f"{data.get('region', 'Unknown')} ({data.get('country', 'Unknown')})",
            'headers': {'User-Agent': 'Mozilla/5.0'}
        }
    async def get_location(self, session, ip):
        try:
            url = self.geo_service['url'].format(ip=ip)
            async with session.get(
                url,
                headers=self.geo_service.get('headers', {}),
                timeout=GEOLOCATION_TIMEOUT
            ) as response:
                data = await response.json()
                LOGGER.info(f"Location API Response: {data}")
                if response.status == 200:
                    return self.geo_service['parser'](data)
                return f"❌ HTTP {response.status}"
        except asyncio.TimeoutError:
            return "⏳ Timeout"
        except Exception as e:
            LOGGER.error(f"Error fetching location: {e}")
            return f"❌ Error ({str(e)[:30]})"
    async def check_anonymity(self, session, proxy_url):
        try:
            async with session.get(
                "http://httpbin.org/headers",
                proxy=proxy_url,
                timeout=PROXY_TIMEOUT,
                headers={'User-Agent': 'Mozilla/5.0'}
            ) as response:
                if response.status == 200:
                    headers_data = await response.json()
                    client_headers = headers_data.get('headers', {})
                    if 'X-Forwarded-For' in client_headers:
                        return 'Transparent'
                    elif 'Via' in client_headers:
                        return 'Anonymous'
                    else:
                        return 'Elite'
                return 'Unknown'
        except:
            return 'Unknown'
    async def check_proxy(self, proxy, proxy_type='http', auth=None):
        result = {
            'proxy': f"{proxy}",
            'status': 'Dead 🔴',
            'location': '• Not determined',
            'anonymity': 'Unknown'
        }
        ip = proxy.split(':')[0]
        try:
            proxy_url = f"{proxy_type}://{auth['username']}:{auth['password']}@{proxy}" if auth else f"{proxy_type}://{proxy}"
            connector = aiohttp.TCPConnector()
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    "http://httpbin.org/ip",
                    proxy=proxy_url,
                    timeout=PROXY_TIMEOUT,
                    headers={'User-Agent': 'Mozilla/5.0'}
                ) as response:
                    data = await response.json()
                    LOGGER.info(f"Proxy Check API Response: {data}")
                    if response.status == 200:
                        result.update({
                            'status': 'Live ✅',
                            'ip': ip
                        })
                        result['anonymity'] = await self.check_anonymity(session, proxy_url)
                    result['location'] = await self.get_location(session, ip)
        except Exception as e:
            LOGGER.error(f"Error checking proxy: {e}")
            async with aiohttp.ClientSession() as session:
                result['location'] = await self.get_location(session, ip)
        return result

checker = HTTPProxyChecker()

async def send_results(client, event, processing_msg, results):
    response = []
    for res in results:
        response.append(f"<b>Proxy:</b> <code>{res['proxy']}</code>\n")
        response.append(f"<b>Status:</b> {res['status']}\n")
        if res['status'] == 'Live ✅':
            response.append(f"<b>Anonymity:</b> {res['anonymity']}\n")
        response.append(f"<b>Region:</b> {res['location']}\n")
        response.append("\n")
    full_response = ''.join(response)
    await processing_msg.edit(full_response, parse_mode="html")

async def px_command_handler(event):
    client = event.client
    user_id = event.sender_id if event.sender else None
    if user_id and await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    args = event.message.text.split()[1:]
    proxies_to_check = []
    if len(args) > 0:
        if len(args) == 1 and args[0].count(':') == 3:
            ip_port, username, password = args[0].rsplit(':', 2)
            proxies_to_check.append(('http', ip_port))
            auth = {'username': username, 'password': password}
        elif len(args) >= 3 and ':' not in args[-1] and ':' not in args[-2]:
            auth = {'username': args[-2], 'password': args[-1]}
            proxy_args = args[:-2]
            for proxy in proxy_args:
                if '://' in proxy:
                    parts = proxy.split('://')
                    if len(parts) == 2 and parts[0].lower() in ['http', 'https']:
                        proxies_to_check.append((parts[0].lower(), parts[1]))
                elif ':' in proxy:
                    proxies_to_check.append(('http', proxy))
        else:
            auth = None
            for proxy in args:
                if '://' in proxy:
                    parts = proxy.split('://')
                    if len(parts) == 2 and parts[0].lower() in ['http', 'https']:
                        proxies_to_check.append((parts[0].lower(), parts[1]))
                elif ':' in proxy:
                    proxies_to_check.append(('http', proxy))
    else:
        if event.message.reply_to and event.message.reply_to.text:
            proxy_text = event.message.reply_to.text
            potential_proxies = proxy_text.split()
            auth = None
            for proxy in potential_proxies:
                if ':' in proxy:
                    if proxy.count(':') == 3:
                        ip_port, username, password = proxy.rsplit(':', 2)
                        proxies_to_check.append(('http', ip_port))
                        auth = {'username': username, 'password': password}
                    else:
                        proxies_to_check.append(('http', proxy))
        else:
            return await event.respond("<b>❌ Provide at least one proxy for check</b>", parse_mode="html")
    if not proxies_to_check:
        return await event.respond("<b>❌ The Proxies Are Not Valid At All</b>", parse_mode="html")
    if len(proxies_to_check) > PROXY_CHECK_LIMIT:
        return await event.respond("<b> ❌ Sorry Bro Maximum Proxy Check Limit Is 20 </b>", parse_mode="html")
    processing_msg = await event.respond("<b> Smart Proxy Checker Checking Proxies 💥</b>", parse_mode="html")
    try:
        tasks = [checker.check_proxy(proxy, proxy_type, auth) for proxy_type, proxy in proxies_to_check]
        results = await asyncio.gather(*tasks)
        await send_results(client, event, processing_msg, results)
    except Exception as e:
        LOGGER.error(f"Error during proxy check: {e}")
        await processing_msg.edit("<b>Sorry Bro Proxy Checker API Dead</b>", parse_mode="html")
        await notify_admin(client, "/px", e, event.message)

def setup_px_handler(app):
    app.add_event_handler(
        px_command_handler,
        events.NewMessage(pattern=f"^{COMMAND_PREFIX}(px|proxy)(?:\s|$)")
    )