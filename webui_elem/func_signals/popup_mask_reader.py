# encoding: utf-8
# @Time   : 2024/3/24
# @Author : Spike
# @Descr   :
from webui_elem.func_signals.__import__ import *


# TODO < -------------------------------- 面具编辑函数注册区 -------------------------------->
def mask_to_chatbot(data):
    population = []
    history = []
    chatbot = []
    for i, item in enumerate(data):
        if i == 0:
            item[0] = 'system'
        elif i % 2 == 0:
            item[0] = 'assistant'
            if item[1]:
                history.append(item[1])
        else:
            item[0] = 'user'
            if item[1]:
                history.append(item[1])
        population.append(item)
    for you, bot in zip(history[0::2], history[1::2]):
        if not you: you = None
        if not bot: bot = None
        chatbot.append([you, bot])
    return population, chatbot, history


def mask_setting_role(data):
    """
    Args:
        data: 为每行数据预设一个角色
    Returns:
    """
    setting_set, zip_chat, _ = mask_to_chatbot(data)
    return setting_set, zip_chat


def mask_del_new_row(data):
    if len(data) == 1:
        return [['system', '']]
    if data:
        return data[:-1]
    else:
        return data


def mask_clear_all(data, state, info):
    if state == 'CANCELED':
        return data
    else:
        return [['system', '']]


def reader_analysis_output(file: gr.File, content, choice, ipaddr: gr.Request):
    """"""
    from crazy_functions.submit_fns import file_reader_content
    from crazy_functions.reader_fns.local_markdown import MdProcessor
    from crazy_functions.reader_fns.local_excel import XlsxHandler
    user_mark = user_client_mark(ipaddr)
    save_path = os.path.join(init_path.private_files_path, user_mark, 'reader')
    if choice == 'Markdown':
        content, status = file_reader_content(file_path=file.name, save_path=save_path, plugin_kwargs={})
        if isinstance(content, list):
            content = to_markdown_tabs(head=content[0], tabs=content[1:], column=True)
        tokens = num_tokens_from_string([content])
        show_value = content
    else:
        data_content = []
        md = MdProcessor(content)
        data_content.extend(md.json_to_list())
        data_content.extend(md.tabs_to_list())
        file_path = XlsxHandler(None, save_path).list_write_to_excel(data_content, 'Reader')
        show_value = html_view_blank(file_path, to_tabs=True)
        tokens = 'file'
    toast = gr.update(value=spike_toast(content=f'Submitting a dialog is expected to consume: `{tokens}`',
                                        title='Completed'), visible=True)
    yield show_value, gr.Textbox.update(label=f'{tokens} Token', value=content), toast
    time.sleep(2)
    yield show_value, gr.Textbox.update(label=f'{tokens} Token', value=content), gr.update(visible=False)
