import json
import requests
import os
import webbrowser
import re
import sys
import subprocess
from urllib.parse import urlparse
import time
import platform

def open_in_vlc(url):
    """Opens the given URL in VLC media player."""
    if platform.system() == "Windows":
        subprocess.Popen(["C:\\Program Files\\VideoLAN\\VLC\\vlc.exe", url])
    else:
        subprocess.run(["vlc", url])

def clean_json(content):
    """Removes trailing commas and invalid control characters from JSON to avoid parsing errors."""
    content = re.sub(r',\s*([}\]])', r'\1', content)  # Remove trailing commas
    content = re.sub(r'[\x00-\x1F\x7F]', '', content)  # Remove control characters
    return content

def validate_json(content):
    """Validates the JSON structure to ensure it can be parsed."""
    try:
        json.loads(content)
        return True
    except json.JSONDecodeError as e:
        print(f"JSON validation error: {e}")
        return False

def revalidate_and_clean_cache(filename):
    """Revalidates and cleans the cached JSON file."""
    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()
    cleaned_content = clean_json(content)
    if validate_json(cleaned_content):
        with open(filename, "w", encoding="utf-8") as file:
            file.write(cleaned_content)
        return json.loads(cleaned_content)
    else:
        raise json.JSONDecodeError("Invalid JSON after revalidating and cleaning cache", cleaned_content, 0)

def get_filename_from_url(url):
    """Generates a safe filename from a URL."""
    parsed_url = urlparse(url)
    filename = os.path.basename(parsed_url.path)
    return filename if filename else "default.w3u"

def fetch_w3u(url):
    """Fetches and loads a .w3u JSON file, caching it locally."""
    filename = get_filename_from_url(url)
    if os.path.exists(filename):
        try:
            return revalidate_and_clean_cache(filename)
        except json.JSONDecodeError as e:
            print(f"Error loading cached file {filename}: {e}")
            os.remove(filename)  # Remove corrupted cache file

    try:
        response = requests.get(url)

        # If the file content starts with "EXTM3U", it's an M3U file, not a JSON file.
        if response.text.strip().startswith("#EXTM3U"):
            confirm = input(f"The file at {url} appears to be an M3U file. Do you want to open it in VLC? (y/n): ").strip().lower()
            if confirm == 'y':
                print(f"Opening {url} in VLC...")
                time.sleep(1)
                open_in_vlc(url)
            return None

        response.raise_for_status()
        response.encoding = 'utf-8'  # Ensure UTF-8 decoding
        cleaned_json = clean_json(response.text)
        
        if not validate_json(cleaned_json):
            raise json.JSONDecodeError("Invalid JSON after cleaning", cleaned_json, 0)
        
        data = json.loads(cleaned_json)
        
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        
        print(f"new file saved in cache: {os.path.abspath(filename)}")
        return data
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"Error fetching {url}: {e}")
        input("Press Enter to continue...")
        return None

def format_url(url):
    """Formats the URL by removing 'https://' and truncating if too long."""
    if url.startswith("https://"):
        url = url[8:]
    #if len(url) > 50:
    #    url = url[:25] + "..." + url[-20:]
    return url

def navigate_w3u(url, history, cache_message=None):
    """Navigates through a .w3u JSON structure."""
    data = fetch_w3u(url)
    if not data:
        return
    
    history.append(url)  # Keep track of navigation history
    
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')  # Clear screen
        sys.stdout.reconfigure(encoding='utf-8')  # Ensure correct encoding for terminal output

        if cache_message:
            print(cache_message)
            cache_message = None

        print(f"{data.get('name', 'Unknown')}")

        groups = data.get("groups", [])
        stations = data.get("stations", [])
        option_index = 0
        options = []

        # Nested groups and stations parsing
        if groups:
            for i, group in enumerate(groups):
                group_url = format_url(group.get("url", "No URL"))
                print(f"[{option_index}] {group.get('name', 'Unnamed Group')} - {group_url}")
                options.append((group, None))
                option_index += 1
                group_stations = group.get("stations", [])
                for j, station in enumerate(group_stations):
                    station_url = format_url(station.get("url", "No URL"))
                    print(f"  [{option_index}] {station.get('name', 'Unnamed Station')} - {station_url}")
                    options.append((station, group))
                    option_index += 1
                # Handle nested groups inside groups
                nested_groups = group.get("groups", [])
                for k, nested_group in enumerate(nested_groups):
                    nested_group_url = format_url(nested_group.get("url", "No URL"))
                    print(f"  [{option_index}] {nested_group.get('name', 'Unnamed Nested Group')} - {nested_group_url}")
                    options.append((nested_group, group))
                    option_index += 1
                    nested_group_stations = nested_group.get("stations", [])
                    for l, nested_station in enumerate(nested_group_stations):
                        nested_station_url = format_url(nested_station.get("url", "No URL"))
                        print(f"    [{option_index}] {nested_station.get('name', 'Unnamed Nested Station')} - {nested_station_url}")
                        options.append((nested_station, nested_group))
                        option_index += 1
        elif stations:
            for i, station in enumerate(stations):
                station_url = format_url(station.get("url", "No URL"))
                print(f"[{option_index}] {station.get('name', 'Unnamed Station')} - {station_url}")
                options.append((station, None))
                option_index += 1

        print("[B] Back")
        print("[Q] Quit")
        
        choice = input("Choose an option: ").strip().lower()
        
        if choice == "q":
            break
        elif choice == "b":
            if len(history) > 1:
                history.pop()
                previous_url = history.pop()  # Get the previous URL
                return navigate_w3u(previous_url, history, cache_message)
            else:
                print("No parent directory.")
                input("Press Enter to continue...")
        elif choice.isdigit() and int(choice) < option_index:
            selected, parent_group = options[int(choice)]
            selected_url = selected.get("url")

            # If a URL matches `https://pastebin.com/*`, it will be treated as `https://pastebin.com/raw/*`
            if selected_url and "pastebin.com" in selected_url and not "raw" in selected_url:
                selected_url = selected_url.replace("pastebin.com", "pastebin.com/raw")

            if selected_url:
                if selected_url.endswith(".w3u") or selected_url.endswith(".json") or "raw.githubusercontent.com" in selected_url or "pastebin.com/raw" in selected_url:
                    navigate_w3u(selected_url, history, cache_message=f"new file saved in cache: {os.path.abspath(get_filename_from_url(selected_url))}\n...\n")
                elif selected_url.endswith(".m3u") or "type=m3u_plus".lower() in selected_url.lower() or selected_url.endswith(".mkv") or selected_url.endswith(".mp4"):
                    print(f"Opening {selected_url} in VLC...")
                    time.sleep(1)
                    open_in_vlc(selected_url)
                else:
                    print(f"Opening {selected_url} in the default web browser...")
                    time.sleep(1)
                    webbrowser.open(selected_url)
        elif not choice:
            # go to the previous page
            if len(history) > 1:
                history.pop()
                previous_url = history.pop()  # Get the previous URL
                return navigate_w3u(previous_url, history, cache_message)
            else:
                print("No parent directory.")
                input("Press Enter to continue...")
        else:
            print("Invalid choice. Try again.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    default_url = "https://xuperlist-1.netlify.app/XUPERLISTS-1.w3u"
    #choice = input(f"Do you want to open the default start file ({default_url})? (y/n): ").strip().lower()
    #if choice == 'n':
    #    start_url = input("Please enter the URL of the .w3u file you want to open: ").strip()
    #else:
    #    start_url = default_url
    start_url = default_url
    navigate_w3u(start_url, [])
