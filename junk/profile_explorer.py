import json

"""
Profile Explorer: Write a simple script that reads the profiles.json file and prints out all available profiles with their storage types and file paths.

"""
# def main(profile: Path):
#     with open(profile, "r") as f:
#         data = json.load(f)
#         print(data)
#         for profile in data["profiles"].values():
#             print(f"profile name: {profile['name']}, storage type: {profile['storage_type']}, file path: {profile['file_path']}")

# if __name__ == "__main__":
#     main(profile = Path(sys.argv[1]))


"""Profile Creator: Create a command-line tool that lets you create a new profile by specifying a name and optional storage type (defaulting to JSON)."""

from pytest_insight.core.storage import StorageProfile


def create_profile(profname: str, storage_type: str = "json") -> None:
    if storage_type == "json":
        prof = StorageProfile(profname, storage_type)
        print(f"Profile '{prof.name}' created with storage type '{prof.storage_type}' and file path '{prof.file_path}'")
        return prof
    else:
        print(f"Unsupported storage type: {storage_type}")


def validate_profiles() -> None:
    with open("/Users/jwr003/.pytest_insight/profiles.json", "r") as f:
        contents = json.load(f)
        if not contents.get("profiles"):
            print("No profiles found in profiles.json")
            return
        for profile in contents["profiles"].values():
            try:
                p = open(profile["file_path"], "r")
                p.close()
            except FileNotFoundError:
                print(f"Profile '{profile['name']}' has invalid file path: {profile['file_path']}")
            except json.JSONDecodeError:
                print(f"Profile '{profile['name']}' has invalid JSON file: {profile['file_path']}")
            except Exception as e:
                print(f"Profile '{profile['name']}' has invalid file path: {profile['file_path']}")
                print(f"Error: {e}")


if __name__ == "__main__":
    validate_profiles()
