from lakedoc import string


def console_input():
    return input(string.color_string('$ ', 'blue')).strip()


def show_all_configs(config: dict):
    print(f"- {string.color_string(' Cookie ', 'green')}\t{'已设置' if config.get('Cookie') else '未设置'}")
    print(f"- {string.color_string('代理地址', 'green')}\t{'已设置' if config.get('代理地址') else '未设置'}")
    print(f"- {string.color_string('保存格式', 'green')}\t{config.get('保存格式')}")


def show_keys_config(config: dict, *keys):
    if not keys:
        return
    for key in keys:
        if key not in config:
            continue
        print(f'{string.color_string("[key]", "green")} {key}')
        print(f'{string.color_string("[val]", "green")} {config[key]}\n')


def show_message(message, level='normal'):
    """
    显示消息
    """
    levels = {
        'normal': 'white',
        'success': 'green',
        'failure': 'red',
        'warning': 'yellow'
    }
    color = levels.get(level, 'white')
    print(string.color_string(message, color))


def show_doc_list(docs, start=None, end=None):
    """
    显示文档列表，支持索引范围查看
    """
    if not docs:
        print("当前没有保存的文档链接")
        return

    # 处理索引范围
    start = 0 if start is None else max(0, start - 1)
    end = len(docs) if end is None else min(len(docs), end)

    for i, doc in enumerate(docs[start:end], start + 1):
        print(f"{i}. {doc}")


def confirm_action(message):
    """
    确认操作
    """
    return input(f"{message} {string.color_string('(y/N)', 'yellow')}: ").lower() == 'y'
