"""
Faceit API Client for CS2 Anti-Cheat
Handles API authentication, fetching match history, and downloading demos.
"""
import gzip
import json
import os
import shutil
import urllib.error
import urllib.request
from typing import List


class FaceitAPI:
    BASE_URL = "https://open.faceit.com/data/v4"

    def __init__(self, api_key: str):
        # Nettoyer la clé au cas où l'utilisateur copie "Bearer " avec
        self.api_key = api_key.strip()
        if self.api_key.lower().startswith("bearer "):
            self.api_key = self.api_key[7:].strip()
            
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

    def _request(self, endpoint: str) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ValueError("Clé API Invalide ou non autorisée.")
            elif e.code == 404:
                raise ValueError("Ressource introuvable (pseudo incorrect ?).")
            else:
                raise Exception(f"Erreur API Faceit ({e.code}) : {e.read().decode()}")
        except Exception as e:
            raise Exception(f"Erreur de connexion Faceit : {e!s}")

    def test_key(self) -> bool:
        """Tests if the API key is valid by querying a generic endpoint."""
        try:
            # We query the games endpoint which is public but requires auth
            self._request("/games?offset=0&limit=1")
            return True
        except ValueError:
            return False

    def get_player_info(self, nickname: str) -> dict:
        """Fetches Faceit player ID by nickname."""
        return self._request(f"/players?nickname={nickname}")

    def get_recent_matches(self, player_id: str, limit: int = 15) -> List[dict]:
        """Fetches recent CS2 matches for a player."""
        data = self._request(f"/players/{player_id}/history?game=cs2&offset=0&limit={limit}")
        return data.get("items", [])

    def get_match_details(self, match_id: str) -> dict:
        """Fetches details of a specific match (including demo URLs)."""
        return self._request(f"/matches/{match_id}")

    @staticmethod
    def download_and_extract_demo(demo_url: str, dest_dem_path: str, progress_callback=None) -> bool:
        """Downloads a .dem.gz file from Faceit and extracts it to a .dem file."""
        gz_path = dest_dem_path + ".gz"
        try:
            # 1. Download
            safe_url = demo_url.strip().replace(" ", "%20")
            if not safe_url.startswith("http"):
                safe_url = "https://" + safe_url
                
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CS2AntiCheat'}
            req = urllib.request.Request(safe_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                total_length = response.headers.get('content-length')
                chunk_size = 1024 * 64  # 64KB chunks
                downloaded = 0
                
                with open(gz_path, 'wb') as out_file:
                    while True:
                        buffer = response.read(chunk_size)
                        if not buffer:
                            break
                        downloaded += len(buffer)
                        out_file.write(buffer)
                        
                        if progress_callback:
                            if total_length:
                                progress_callback(downloaded / int(total_length), "Téléchargement...")
                            else:
                                # Si pas de Content-Length, on affiche au moins les Mo téléchargés
                                progress_callback(0.0, f"Téléchargé : {downloaded // (1024*1024)} Mo")
            
            # 2. Extract
            if progress_callback:
                progress_callback(1.0, "Extraction de l'archive...")
                
            MAX_EXTRACT_SIZE = 500 * 1024 * 1024  # 500 MB limit
            extracted_size = 0
            with gzip.open(gz_path, 'rb') as f_in:
                with open(dest_dem_path, 'wb') as f_out:
                    while True:
                        chunk = f_in.read(1024 * 64)
                        if not chunk:
                            break
                        extracted_size += len(chunk)
                        if extracted_size > MAX_EXTRACT_SIZE:
                            raise ValueError("Démo trop volumineuse (zip bomb potentielle).")
                        f_out.write(chunk)
                    
            # 3. Clean up
            os.remove(gz_path)
            return True
            
        except Exception as e:
            if os.path.exists(gz_path):
                try: os.remove(gz_path)
                except: pass
            if os.path.exists(dest_dem_path):
                try: os.remove(dest_dem_path)
                except: pass
            raise Exception(f"Erreur téléchargement/extraction : {e}")
