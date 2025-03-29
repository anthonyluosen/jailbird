import os

def get_folder_contents(folder_path):
    """获取文件夹中的文件和子文件夹"""
    folders = []
    files = []

    try:
        items = os.listdir(folder_path)
        for item in items:
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path):
                folders.append(item)
            elif item.endswith('.txt'):
                files.append(item)
    except FileNotFoundError:
        pass

    return folders, files 