import os
import asyncio
import aiohttp
import aiofiles
import aiofiles.os
from telethon import events
from config import COMMAND_PREFIX, BAN_REPLY
from utils import LOGGER, notify_admin
from core import banned_users

async def fetch_github_api(session, url):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    except:
        return None

async def get_repo_branches(session, repo_url):
    try:
        parts = repo_url.rstrip('/').split('/')
        user_name, repo_name = parts[-2], parts[-1].replace('.git', '')
        api_url = f"https://api.github.com/repos/{user_name}/{repo_name}/branches"
        branches_data = await fetch_github_api(session, api_url)
        if not branches_data:
            return None
        return [branch['name'] for branch in branches_data]
    except:
        return None

async def get_github_repo_details(session, repo_url):
    try:
        parts = repo_url.rstrip('/').split('/')
        user_name, repo_name = parts[-2], parts[-1].replace('.git', '')
        api_url = f"https://api.github.com/repos/{user_name}/{repo_name}"
        repo_data = await fetch_github_api(session, api_url)
        if not repo_data:
            return None
        return {
            'forks_count': repo_data.get('forks_count', 0),
            'description': repo_data.get('description', 'No description available'),
            'default_branch': repo_data.get('default_branch', 'main')
        }
    except:
        return None

async def download_repo_zip(session, repo_url, branch, clone_dir):
    try:
        parts = repo_url.rstrip('/').split('/')
        user_name, repo_name = parts[-2], parts[-1].replace('.git', '')
        zip_url = f"https://api.github.com/repos/{user_name}/{repo_name}/zipball/{branch}"
        async with session.get(zip_url) as response:
            response.raise_for_status()
            zip_path = f"{clone_dir}.zip"
            os.makedirs(os.path.dirname(zip_path), exist_ok=True)
            async with aiofiles.open(zip_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(8192)
                    if not chunk:
                        break
                    await f.write(chunk)
            return zip_path
    except:
        return None

async def normalize_url(repo_url):
    repo_url = repo_url.strip()
    if not repo_url.startswith(('http://', 'https://')):
        repo_url = f"https://{repo_url}"
    if not repo_url.endswith('.git'):
        repo_url = f"{repo_url.rstrip('/')}.git"
    return repo_url

async def git_download_handler(event):
    user_id = event.sender_id
    if await banned_users.find_one({"user_id": user_id}):
        await event.respond(BAN_REPLY)
        return
    args = event.raw_text.split()
    if len(args) < 2:
        await event.respond("<b>Provide a valid GitHub repository URL.</b>", parse_mode="html")
        return
    repo_url = await normalize_url(args[1])
    requested_branch = args[2] if len(args) > 2 else None
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 5 or parts[2] != "github.com":
        await event.respond("<b>Provide a valid GitHub repository URL.</b>", parse_mode="html")
        return
    status_msg = await event.respond("<b>Downloading repository, please wait...</b>", parse_mode="html")
    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=50),
        timeout=aiohttp.ClientTimeout(total=30)
    ) as session:
        try:
            user_name, repo_name = parts[-2], parts[-1].replace('.git', '')
            repo_details_task = get_github_repo_details(session, repo_url)
            branches_task = get_repo_branches(session, repo_url)
            repo_details, branches = await asyncio.gather(repo_details_task, branches_task)
            if not branches or not repo_details:
                raise Exception("Repository is private or inaccessible")
            forks_count = repo_details['forks_count']
            description = repo_details['description']
            if requested_branch:
                if requested_branch not in branches:
                    raise Exception(f"Branch '{requested_branch}' not found")
                branch = requested_branch
            else:
                branch = "main" if "main" in branches else "master" if "master" in branches else branches[0]
            clone_dir = f"repos/{repo_name}_{branch}"
            zip_path = await download_repo_zip(session, repo_url, branch, clone_dir)
            if not zip_path:
                raise Exception("Failed to download repository zip")
            repo_info = (
                "<b>📁 Repository Details</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Owner:</b> <code>{user_name}</code>\n"
                f"📂 <b>Name:</b> <code>{repo_name}</code>\n"
                f"🔀 <b>Forks:</b> <code>{forks_count}</code>\n"
                f"🌿 <b>Branch:</b> <code>{branch}</code>\n"
                f"🔗 <b>URL:</b> <code>{repo_url}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>Description:</b>\n<code>{description}</code>\n\n"
                f"🌱 <b>Branches:</b> <code>{', '.join(branches)}</code>"
            )
            await status_msg.delete()
            await event.respond(
                repo_info,
                file=zip_path,
                parse_mode="html"
            )
        except Exception as e:
            LOGGER.error(f"Error in /git: {str(e)}")
            await notify_admin(event.client, "/git", e, event)
            await event.respond("<b>Provide a valid GitHub repository URL.</b>", parse_mode="html")
        finally:
            try:
                if 'zip_path' in locals() and os.path.exists(zip_path):
                    await aiofiles.os.remove(zip_path)
            except:
                pass

def setup_git_handler(client):
    @client.on(events.NewMessage(pattern=f"^{COMMAND_PREFIX}git(?: |$)(.*)"))
    async def handler(event):
        await git_download_handler(event)
