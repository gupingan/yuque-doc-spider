import json
import os


class Model:
    def __init__(self):
        self.config_file = 'config.json'
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'Cookie': '',
            '代理地址': '',
            '保存格式': 'markdown',
            '链接': [],
            'Headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                'Host': 'www.yuque.com'
            }
        }

    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)

    def get_doc_links(self):
        return self.config['链接']

    def add_doc_link(self, link):
        if link not in self.config['链接']:
            self.config['链接'].append(link)
            self.save_config()

    def remove_doc_link(self, link):
        if link in self.config['链接']:
            self.config['链接'].remove(link)
            self.save_config()
            return True
        return False

    def pop_doc_link(self, index):
        if index < 0 or index >= len(self.config['链接']):
            return False
        self.config['链接'].pop(index)
        self.save_config()
        return True

    def clear_doc_links(self):
        self.config['链接'] = []
        self.save_config()
