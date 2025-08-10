import asyncio
import logging
import re
from typing import List, Tuple, Dict, Any
from bs4 import BeautifulSoup
import aiohttp

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AceStreamScraper:
    """Scraper for Acestream links from archive.org HTML page"""
    
    def __init__(self, url: str, timeout: int = 10, retries: int = 3):
        self.url = url
        self.timeout = timeout
        self.retries = retries
        self.acestream_pattern = re.compile(r'acestream://([\w\d]+)')
        self.identified_ids = set()
        self.headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def fetch_content(self, url: str) -> str:
        """Fetch content from URL"""
        logger.info(f"Fetching content from: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, 
                                     headers=self.headers,
                                     timeout=self.timeout) as response:
                    response.raise_for_status()
                    content = await response.text()
                    logger.info(f"Successfully fetched content ({len(content)} bytes)")
                    return content
        except Exception as e:
            logger.error(f"Error fetching content from {url}: {str(e)}")
            raise

    def extract_from_script(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """Extract acestream links from linksData in script tags"""
        channels = []
        
        # Find script tag with linksData
        script_tag = soup.find('script', text=re.compile(r'const linksData'))
        if script_tag:
            script_content = script_tag.string
            json_match = re.search(r'const linksData\s*=\s*(\{.*?\}\s*);', script_content, re.DOTALL)
            
            if json_match:
                # Extract the JSON part
                json_text = json_match.group(1)
                
                # Extract links using regex to avoid JSON parsing
                links_matches = re.finditer(r'\{\s*"name":\s*"(.*?)",\s*"url":\s*"(acestream://[\w\d]+)"\s*\}', json_text)
                
                for match in links_matches:
                    name = match.group(1)
                    url = match.group(2)
                    channel_id = url.split('acestream://')[1]
                    
                    if channel_id and channel_id not in self.identified_ids:
                        channels.append((channel_id, name))
                        self.identified_ids.add(channel_id)
        
        return channels

    async def scrape(self) -> List[Tuple[str, str]]:
        """Main scraping method"""
        channels = []
        retries_left = self.retries
        
        while retries_left >= 0:
            try:
                content = await self.fetch_content(self.url)
                soup = BeautifulSoup(content, 'html.parser')
                
                # Extract from script
                script_channels = self.extract_from_script(soup)
                channels.extend(script_channels)
                
                logger.info(f"Successfully extracted {len(channels)} channels")
                return channels
                
            except Exception as e:
                logger.error(f"Error scraping {self.url}: {str(e)}")
                retries_left -= 1
                if retries_left < 0:
                    logger.error("Max retries reached")
                    break
                self.timeout += 5
        
        return channels

    def format_output(self, channels: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Format output channels as dictionaries"""
        return [{"name": name, "id": channel_id} for channel_id, name in channels]

    def save_to_file(self, channels: List[Tuple[str, str]], filename: str = "acestream_channels.txt"):
        """Save channels to M3U playlist format"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for channel_id, name in channels:
                f.write(f"#EXTINF:-1,{name}\n")
                f.write(f"http://127.0.0.1:6878/ace/getstream?id={channel_id}\n")
        logger.info(f"Saved {len(channels)} channels to M3U playlist {filename}")

    def save_to_m3u(self, channels: List[Tuple[str, str]], filename: str = "acestream_playlist.m3u"):
        """Save channels to M3U playlist format"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for channel_id, name in channels:
                f.write(f"#EXTINF:-1,{name}\n")
                f.write(f"acestream://{channel_id}\n")
        logger.info(f"Saved {len(channels)} channels to M3U playlist {filename}")

async def main():
    url = "https://archive.org/download/abcd_20240416/output.html"
    scraper = AceStreamScraper(url)
    
    channels = await scraper.scrape()
    
    if channels:
        print(f"Found {len(channels)} channels:")
        for i, (channel_id, name) in enumerate(channels[:10], 1):
            print(f"{i}. {name}: acestream://{channel_id}")
        
        if len(channels) > 10:
            print(f"...and {len(channels) - 10} more channels")
        
        # Save channels to files
        scraper.save_to_file(channels)
        scraper.save_to_m3u(channels)
    else:
        print("No channels found")

if __name__ == "__main__":
    asyncio.run(main())

