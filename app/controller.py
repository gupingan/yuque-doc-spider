import platform
import time
import re
import json
import os
import pathlib
import sys
import requests
import lakedoc
from lakedoc import string
from urllib import parse
from app import model
from app import view
from app import __doc__

try:
    import readline
except ImportError:
    import pyreadline3 as readline


class Util:
    @staticmethod
    def get_path_array(url):
        parsed_url = parse.urlparse(url)
        path_parts = [p for p in parsed_url.path.strip('/').split('/') if p]
        return path_parts

    @staticmethod
    def extract_doc_url(url, default=None):
        path_parts = Util.get_path_array(url)
        if len(path_parts) == 3:
            return path_parts[-1]

        return default

    @staticmethod
    def is_valid_domain(url, allowed_domains=None):
        parsed_url = parse.urlparse(url)
        domain = parsed_url.netloc
        if allowed_domains:
            return any(domain.endswith(allowed_domain) for allowed_domain in allowed_domains)
        return True

    @staticmethod
    def set_console_encoding():
        if sys.platform.startswith('win'):
            os.system('chcp 65001')

    @staticmethod
    def clear_screen():
        if sys.platform.startswith('win'):
            os.system('cls')
        else:
            os.system('clear')

    @staticmethod
    def set_console_title(title):
        if platform.system() == "Windows":
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        elif platform.system() in ["Linux", "Darwin"]:
            os.system(f"echo -n -e '\033]0;{title}\007'")


class TocParser:
    def __init__(self, book_id, book_name, toc_data):
        self.book_id = book_id
        self.book_name = book_name
        self._toc_data = toc_data
        self._mappings = {item['uuid']: item for item in toc_data}
        self.folder_path = {}

    @property
    def outline(self):
        outline = []
        for toc in self._toc_data:
            suffix = '\t' * toc.get('level', 0)
            outline.append(f'{suffix}- {toc.get("title", "未提取到标题")}')

        return '\n'.join(outline)

    @property
    def result(self):
        """解析目录结构，提取所有DOC类型的项目"""
        # 构建文件夹路径
        for item in self._toc_data:
            if item['type'] == 'TITLE':
                self._build_mappings(item)

        # 提取所有 DOC 类型的项目
        return [
            {
                'folder': self._get_folder_path(item),
                'url': item['url'],
                'doc_id': item['doc_id'],
                'title': item['title'],
                'book_id': self.book_id,
                'book_name': self.book_name,
            }
            for item in self._toc_data
            if item['type'] == 'DOC'
        ]

    def _build_mappings(self, item, current_path='/'):
        """递归构建文件夹路径"""
        self.folder_path[item['uuid']] = current_path

        # 处理子项目
        if item.get('child_uuid'):
            child = self._mappings[item['child_uuid']]
            child_path = f"{current_path}{item['title']}/"
            self._build_mappings(child, child_path)

        # 处理兄弟项目
        if item.get('sibling_uuid'):
            sibling = self._mappings[item['sibling_uuid']]
            if sibling['type'] == 'TITLE':
                self._build_mappings(sibling, current_path)

    def _get_folder_path(self, item):
        """获取DOC类型项目的完整文件夹路径"""
        if not item['parent_uuid']:
            return '/'

        path = []
        current = item
        while current.get('parent_uuid'):
            parent = self._mappings[current['parent_uuid']]
            if parent['type'] == 'TITLE':
                path.append(parent['title'])
            current = parent

        return '/' + '/'.join(reversed(path)) + '/'


class Console:
    def __init__(self, func=None, tip=None, example=None):
        self.func = func
        self.tip = tip
        self.example = example

    def __call__(self, *args, **kwargs):
        if not self.func:
            return
        return self.func(*args, **kwargs)

    def help(self, show_example=False):
        help_text = f"功能：\n\t{self.tip}\n" if show_example else f"{self.tip}\n"
        if show_example and self.example:
            help_text += f"示例:\n{self.example}"
        return help_text.strip()


class Controller:
    def __init__(self):
        self.model = model.Model()
        self._operates = {
            'show': Console(
                self.show_links, '显示链接',
                "\tshow             \t显示所有链接"
                "\n\tshow :5         \t显示前5行链接"
                "\n\tshow 3:         \t显示第3行及其后面的链接"
                "\n\tshow 2:4        \t显示第2至4行的链接"),
            'add': Console(
                self.add_links, '添加链接',
                "\tadd link1...      \t添加指定的链接"),
            'rem': Console(
                self.remove_links, '删除链接',
                "\trem link1...      \t删除指定的链接"
                "\n\trem 1 3         \t删除第1、3行的链接"
                "\n\trem 2 link1...  \t可混合使用序号及链接"),
            'clear': Console(
                self.clear_links, '清空链接',
                "\tclear             \t清空所有的链接，没有额外参数"),
            'config': Console(
                self.show_config, '显示配置',
                "\tconfig            \t显示所有的配置"
                "\n\tconfig k1 k2    \t查看指定的配置及其值"
                f"\n\t{string.color_string('当前可查看的 key：Cookie|代理地址|保存格式|Headers|链接', 'yellow')}"),
            'set': Console(
                self.set_config, '设置某项配置的值',
                "\tset key val       \t为指定的键设置值"
                f"\n\t{string.color_string('当前仅支持的 key：Cookie|代理地址|保存格式', 'yellow')}"),
            'start': Console(
                self.start_scraping, '获取链接指向的文档',
                "\tstart             \t获取所有链接的文档"
                "\n\tstart :5        \t获取前5行链接的文档"
                "\n\tstart 3:        \t获取第3行链接及其之后的文档"
                "\n\tstart 2:4       \t获取第2至4行链接的文档"),
            'cls': Console(
                Util.clear_screen, '清空控制台',
                "\tcls               \t清空控制台的日志、命令等信息"),
            'help': Console(
                self.show_help, '显示命令帮助',
                "\thelp              \t显示所有命令的功能作用"
                "\n\thelp <命令操作>     \t显示具体命令的功能作用及其示例")
        }
        self._exit_codes = {'exit', 'quit', '0', '-1', 'exit()', 'quit()', '退出'}
        self.setup_autocomplete()

    def setup_autocomplete(self):
        def completer(text, state):
            options = [cmd for cmd in self._operates.keys() if cmd.startswith(text)]
            if state < len(options):
                return options[state]
            else:
                return None

        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")

    def run(self):
        Util.set_console_encoding()
        Util.clear_screen()
        view.show_message(__doc__)

        while True:
            try:
                command = view.console_input()
                parts = [p.strip() for p in command.split() if p]
            except KeyboardInterrupt:
                parts = ['exit']

            if not parts:
                continue

            operate = parts[0]
            if operate in self._exit_codes:
                view.show_message('感谢使用，再见！', 'success')
                break

            if not self._operates.get(operate):
                continue

            self._operates[operate](*parts[1:])

    def show_links(self, *args):
        docs = self.model.get_doc_links()

        if not args:
            view.show_doc_list(docs)
            return

        if len(args) > 1:
            view.show_message("该命令的参数最多为1位", 'failure')
            return

        arg = str(args[0])
        if ':' not in arg:
            view.show_message("区间范围格式有误", 'failure')
            return

        start, end = arg.split(':', 1)
        start = int(start) if start.isdigit() else None
        end = int(end) if end.isdigit() else None

        view.show_doc_list(docs, start, end)

    def add_links(self, *links):
        for link in links:
            if not (Util.is_valid_domain(link, ['yuque.com'])
                    and 2 <= len(Util.get_path_array(link)) <= 3):
                view.show_message(f"链接 `{link}` 无效，无法添加", 'failure')
                continue

            self.model.add_doc_link(link)
            view.show_message(f"链接`{link}`添加成功", 'success')

    def remove_links(self, *options):
        for option in options:
            result = self.model.pop_doc_link(int(option) - 1) \
                if option.isdigit() \
                else self.model.remove_doc_link(option)

            view.show_message("链接删除成功" if result else "删除失败，指定的链接可能不存在", 'failure')

    def clear_links(self, *args):
        if len(args) > 0:
            view.show_message("该命令无需参数", 'failure')
            return
        if view.confirm_action("确定要清空所有链接吗？"):
            self.model.clear_doc_links()
            view.show_message("所有链接已清空", 'success')

    def show_config(self, *keys):
        show_all = not keys
        if show_all:
            view.show_all_configs(self.model.config)
        else:
            view.show_keys_config(self.model.config, *keys)

    def set_config(self, *key_val):
        if len(key_val) != 2:
            view.show_message('仅支持`set key val`格式，参数仅有2位', 'failure')
            return

        key = key_val[0]
        val = key_val[1]

        if key in ('Cookie', '代理地址'):
            is_changed = True
        elif key == '保存格式':
            if val not in ('html', 'markdown'):
                view.show_message('保存格式仅支持html、markdown', 'failure')
                return
            is_changed = True
        else:
            view.show_message(f'指定的配置`{key}`不存在或者不支持设置', 'failure')
            return

        if is_changed:
            self.model.config[key] = val
            self.model.save_config()
            view.show_message(f'已将`{key}`设置为：{val}', 'success')

    def start_scraping(self, *args):
        doc_links = self.model.config.get('链接', [])
        if not doc_links:
            return

        urls = self._parse_scraping_args(doc_links, args)
        if not urls:
            return

        if not self.model.config.get('Cookie'):
            view.show_message('请先设置Cookie，否则无法获取文档内容', 'failure')
            return

        view.show_message('准备获取文档就绪，可按下`Ctrl + C`快捷键终止')
        for url in urls:
            try:
                toc_parser = self._build_toc_parser(url)
                if not toc_parser:
                    continue
                view.show_message(f'开始转存文档库`{toc_parser.book_name}`({url})', 'success')
                doc_url = Util.extract_doc_url(url)
                self._process_doc_parser(doc_url, toc_parser)
                time.sleep(0.5)
            except KeyboardInterrupt:
                view.show_message('已终止文档库的获取', 'warning')
                break

    @staticmethod
    def _parse_scraping_args(doc_links, args: tuple):
        if not args:
            return doc_links

        if len(args) > 1:
            view.show_message('该命令的参数最多为1位', 'failure')
            return None

        doc_links_length = len(doc_links)
        arg = str(args[0])
        if arg.isdigit():
            index = int(arg)
            if 1 <= index <= doc_links_length:
                return [doc_links[index - 1]]
        elif ':' in arg:
            start, end = map(lambda x: int(x) if x.isdigit() else None, arg.split(':')[:2])
            start = max(0, start - 1) if start else 0
            end = min(doc_links_length, end) if end else doc_links_length
            return doc_links[start:end]

        view.show_message('不支持的索引/区间格式', 'failure')
        return None

    def _build_toc_parser(self, url: str):
        """构建目录解析器"""
        if not (Util.is_valid_domain(url, ['yuque.com'])
                and 2 <= len(Util.get_path_array(url)) <= 3):
            view.show_message(f'链接`{url}`无效，无法抓取', 'failure')
            return

        # 设置请求头
        headers = self.model.config.get('Headers', {})
        cookie = self.model.config.get('Cookie', '')
        headers['Cookie'] = cookie
        # 设置代理
        proxy = self.model.config.get('代理地址') or None
        proxies = {'http': proxy, 'https': proxy}
        # 发起请求
        response = requests.request('GET', url, headers=headers, proxies=proxies)
        # 初步解析
        match_result = re.findall(r'decodeURIComponent\("(.*)"\)', response.text)
        raw_data = match_result[0] if match_result else None
        if not raw_data:
            return
        page_data = json.loads(parse.unquote(raw_data))
        book = page_data.get('book', {})
        if not book:
            return
        book_id = book.get('id', '')
        book_name = book.get('name')
        book_toc = book.get('toc', [])
        if not (book_id and book_name and book_toc):
            return
        return TocParser(book_id, book_name, book_toc)

    def _process_doc_parser(self, doc_url: str, toc_parser: TocParser):
        """处理目录解析器的相关数据"""
        base_dir = pathlib.Path(f'./output/{self._sanitize_filename(toc_parser.book_name)}/')
        base_dir.mkdir(parents=True, exist_ok=True)
        toc_file = base_dir / '目录.txt'
        with open(toc_file, 'w', encoding='utf-8') as fw:
            fw.write(toc_parser.outline)
        view.show_message(f'目录已创建，路径为：{str(toc_file.absolute().resolve())}', 'warning')

        book_docs = toc_parser.result
        for doc in book_docs:
            try:
                if doc_url is None:
                    content = self._get_doc_content(doc)
                    self._save_content_in_folder(content, doc, base_dir)
                    continue

                if doc.get('url') == doc_url:
                    content = self._get_doc_content(doc)
                    self._save_content_in_folder(content, doc, base_dir)
                    return
            except Exception as e:
                view.show_message(f'处理文档`{doc}`报错：{e}', 'failure')

    def _get_doc_content(self, doc: dict):
        """获取指定文档的内容"""
        doc_url = doc.get('url')
        book_id = doc.get('book_id')
        if not (doc_url and book_id):
            return
        url = (f'https://www.yuque.com/api/docs/{doc_url}?include_contributors=true'
               f'&include_like=true&include_hits=true&merge_dynamic_data=false&book_id={book_id}')
        # 设置请求头
        headers = self.model.config.get('Headers', {})
        cookie = self.model.config.get('Cookie', '')
        headers['Cookie'] = cookie
        # 设置代理
        proxy = self.model.config.get('代理地址') or None
        proxies = {'http': proxy, 'https': proxy}
        response = requests.request('GET', url, headers=headers, proxies=proxies)
        try:
            data = response.json().get('data')
        except (ValueError, KeyError, TypeError):
            data = {}
        return data.get('content')

    def _save_content_in_folder(self, content, doc, folder):
        """保存内容到指定文件夹"""
        if not content:
            return

        doc_folder = doc.get('folder', '/')
        save_folder = pathlib.Path(f'{str(folder)}{doc_folder}')
        save_folder.mkdir(parents=True, exist_ok=True)

        doc_title = doc.get('title', '未提取到标题')
        safe_title = self._sanitize_filename(doc_title)
        save_format = self.model.config.get('保存格式')
        if save_format == 'markdown':
            save_path = save_folder / f'{safe_title}.md'
            lakedoc.convert(content, save_path, is_file=False, builder='lxml', title=f'# {doc_title}')
            view.show_message(f'文档已保存：{str(save_path.absolute().resolve())}')
        elif save_format == 'html':
            save_path = save_folder / f'{safe_title}.html'
            with open(save_path, 'w', encoding='utf-8') as fw:
                fw.write(content)
            view.show_message(f'文档已保存：{str(save_path.absolute().resolve())}')

    @staticmethod
    def _sanitize_filename(filename):
        """将文件名转换为安全的文件名"""
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.strip()
        if not filename:
            filename = "untitled"
        return filename[:255]

    def show_help(self, *args):
        if len(args) > 1:
            view.show_message("无效的help命令，格式为：help 或 help <操作符>", 'warning')
            return

        if not args:
            # 显示所有操作的帮助信息，不包括示例
            for op, console in self._operates.items():
                view.show_message(f"{op}     \t{console.help()}")
        elif args[0] in self._operates:
            # 显示特定操作的帮助信息，包括示例
            console = self._operates[args[0]]
            view.show_message(console.help(show_example=True))
        else:
            view.show_message(f"未知的操作符`{args[0]}`", 'failure')
