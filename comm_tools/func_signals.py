#! .\venv\
# encoding: utf-8
# @Time   : 2023/9/2
# @Author : Spike
# @Descr   :
import os, random
import copy
import gradio as gr
import time
import Levenshtein

from concurrent.futures import ThreadPoolExecutor
from comm_tools import toolbox
from comm_tools.database_processor import SqliteHandle
from comm_tools import func_box

# 处理latex options
user_latex_option, = toolbox.get_conf('latex_option')
if user_latex_option == "default":
    latex_delimiters_set = [
        {"left": "$$", "right": "$$", "display": True},
        {"left": "$", "right": "$", "display": False},
        {"left": "\\(", "right": "\\)", "display": False},
        {"left": "\\[", "right": "\\]", "display": True},
    ]
elif user_latex_option == "strict":
    latex_delimiters_set = [
        {"left": "$$", "right": "$$", "display": True},
        {"left": "\\(", "right": "\\)", "display": False},
        {"left": "\\[", "right": "\\]", "display": True},
    ]
elif user_latex_option == "all":
    latex_delimiters_set = [
        {"left": "$$", "right": "$$", "display": True},
        {"left": "$", "right": "$", "display": False},
        {"left": "\\(", "right": "\\)", "display": False},
        {"left": "\\[", "right": "\\]", "display": True},
        {"left": "\\begin{equation}", "right": "\\end{equation}", "display": True},
        {"left": "\\begin{align}", "right": "\\end{align}", "display": True},
        {"left": "\\begin{alignat}", "right": "\\end{alignat}", "display": True},
        {"left": "\\begin{gather}", "right": "\\end{gather}", "display": True},
        {"left": "\\begin{CD}", "right": "\\end{CD}", "display": True},
    ]
elif user_latex_option == "disabled":
    latex_delimiters_set = []
else:
    latex_delimiters_set = [
        {"left": "$$", "right": "$$", "display": True},
        {"left": "$", "right": "$", "display": False},
        {"left": "\\(", "right": "\\)", "display": False},
        {"left": "\\[", "right": "\\]", "display": True},
    ]


def spinner_chatbot_loading(chatbot):
    loading = [''.join(['.' * random.randint(1, 5)])]
    # 将元组转换为列表并修改元素
    loading_msg = copy.deepcopy(chatbot)
    temp_list = list(loading_msg[-1])

    temp_list[1] = func_box.pattern_html(temp_list[1]) + f'{random.choice(loading)}'
    # 将列表转换回元组并替换原始元组
    loading_msg[-1] = tuple(temp_list)
    return loading_msg


def filter_database_tables():
    tables = SqliteHandle(database='ai_prompt.db').get_tables()
    preset = toolbox.get_conf('preset_prompt')[0]['key']
    split_tab = []
    for t in tables:
        if str(t).startswith('prompt_') and str(t).endswith('_sys'):
            split_tab.append("_".join(str(t).split('_')[1:-1]))
    split_tab_new = ['新建分类'] + preset + split_tab
    return split_tab_new


# TODO < -------------------------------- 对话函数注册区 ----------------------------------->
def clear_input(inputs, cookies, select, ipaddr: gr.Request):
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    file_list, only_name, new_path, new_name = func_box.get_files_list(user_path, filter_format=['.json'])
    index = 2
    if not cookies.get('first_chat'):
        select_file = inputs
        while select_file in only_name:  # 重名处理
            select_file = f"{index}_{inputs}"
            index += 1
        cookies['first_chat'] = func_box.replace_special_chars(str(select_file)[:10])
        only_name = [cookies['first_chat']] + only_name
    output = ['', inputs, gr.update(visible=True), gr.update(visible=False),
              gr.Radio.update(choices=only_name, value=cookies['first_chat'])]
    return output


def clear_chat_cookie(cookie, ipaddr: gr.Request):
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    file_list, only_name, new_path, new_name = func_box.get_files_list(user_path, filter_format=['.json'])
    default_params, = toolbox.get_conf('LLMS_DEFAULT_PARAMETER')
    llms_combo = [cookie.get(key, default_params[key]) for key in default_params]
    output = [[], [], cookie, *llms_combo+[''],  '已重置对话记录和对话Cookies',
              gr.Radio.update(choices=['新对话']+only_name, value='新对话'), "新对话"]
    return output


def select_history(select, cookies, ipaddr: gr.Request):
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    user_history = [f for f in os.listdir(user_path) if f.endswith('.json') and select == os.path.splitext(f)[0]]
    if not user_history:
        return [], []
    history_handle = func_box.HistoryJsonHandle(os.path.join(user_path, user_history[0]))
    history_update_combo = history_handle.update_for_history(cookies, select)
    return [*history_update_combo, select]


def rename_history(old_file, filename: str,  ipaddr: gr.Request):
    filename = filename.strip(' \n')
    if filename == "":
        return gr.update()
    if not filename.endswith(".json"):
        filename += ".json"
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    full_path = os.path.join(user_path, filename)
    if not os.path.exists(os.path.join(user_path, f"{old_file}.json")):
        return gr.Error(f'{old_file}历史文件不存在，请刷新页面后尝试')
    repeat_file_index = 2
    while os.path.exists(full_path):     # 命名重复检测
        full_path = os.path.join(user_path, f"{repeat_file_index}_{filename}")
        repeat_file_index += 1
    os.rename(os.path.join(user_path, f"{old_file}.json"), full_path)
    file_list, only_name, new_path, new_name = func_box.get_files_list(user_path, filter_format=['.json'])
    return gr.Radio.update(choices=only_name, value=new_name)


def delete_history(cookies, filename, ipaddr: gr.Request):
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    full_path = os.path.join(user_path, f"{filename}.json")
    if not os.path.exists(full_path):
        if filename == 'CANCELED':
            return gr.update()
        else:
            raise gr.Error('文件或许已不存在')
    os.remove(full_path)
    file_list, only_name, new_path, new_name = func_box.get_files_list(os.path.join(func_box.history_path, ipaddr.client.host), filter_format=['.json'])
    history_handle = func_box.HistoryJsonHandle(new_path)
    history_update_combo = history_handle.update_for_history(cookies, new_name)
    return [gr.Radio.update(choices=only_name, value=new_name), *history_update_combo]


def import_history(file, ipaddr: gr.Request):
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    os.rename(file.name, os.path.join(user_path, os.path.basename(file.name)))
    file_list, only_name, new_path, new_name = func_box.get_files_list(user_path, filter_format=['.json'])
    return gr.Radio.update(choices=only_name, value=new_name)


def refresh_history(ipaddr: gr.Request):
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    file_list, only_name, new_path, new_name = func_box.get_files_list(user_path, filter_format=['.json'])
    return gr.Radio.update(choices=only_name, value=new_name)


# TODO < -------------------------------- 小按钮函数注册区 -------------------------------->
def delete_latest_chat(chatbot, history, cookies: dict, ipaddr: gr.Request):
    select = cookies.get('first_chat', '')
    user_path = os.path.join(func_box.history_path, ipaddr.client.host, f"{select}.json")
    history_handle = func_box.HistoryJsonHandle(user_path)
    history_handle.delete_the_latest_chat()
    history_update_combo = history_handle.update_for_history(cookies, select)
    return history_update_combo


def get_user_upload(chatbot, txt, ipaddr: gr.Request):
    """
    获取用户上传过的文件
    """
    private_upload = './private_upload'
    user_history = os.path.join(private_upload, ipaddr.client.host)
    history = """| 编号 | 目录 | 目录内文件 |\n| --- | --- | --- |\n"""
    count_num = 1
    for root, d, file in os.walk(user_history):
        if txt in str(file) or txt in root:
            file_link = "<br>".join([f'{func_box.html_view_blank(f"{root}/{i}")}' for i in file])
            history += f'| {count_num} | {root} | {file_link} |\n'
            count_num += 1
    chatbot.append([None,  # 'Load Submission History like `{txt}`....',
                    f'{history}\n\n'
                    f'[Local Message] 请自行复制以上目录 or 目录+文件, 填入输入框以供函数区高亮按钮使用\n\n'
                    f'{func_box.html_tag_color("提交前记得请检查头尾空格哦～")}\n\n'])
    return chatbot


# TODO < -------------------------------- 基础功能函数注册区 -------------------------------->
def prompt_retrieval(is_all, hosts='', search=False):
    """
    上传文件，将文件转换为字典，然后存储到数据库，并刷新Prompt区域
    Args:
        is_all： prompt类型
        hosts： 查询的用户ip
        search：支持搜索，搜索时将key作为key
    Returns:
        返回一个列表
    """
    all_, personal = toolbox.get_conf('preset_prompt')[0]['key']
    count_dict = {}
    hosts = func_box.non_personal_tag(is_all, hosts)
    if all_ == is_all:
        for tab in SqliteHandle('prompt_').get_tables():
            if tab.startswith('prompt'):
                data, source = SqliteHandle(tab).get_prompt_value(None)
                if data: count_dict.update(data)
    elif personal == is_all:
        data, source = SqliteHandle(f'prompt_{hosts}').get_prompt_value(None)
        if data: count_dict.update(data)
    elif hosts and is_all != '新建分类':
        data, source = SqliteHandle(f'prompt_{hosts}').get_prompt_value(None)
        if data: count_dict.update(data)
    retrieval = []
    if count_dict != {}:
        for key in count_dict:
            if not search:
                retrieval.append([key, count_dict[key]])
            else:
                retrieval.append([count_dict[key], key])
        return retrieval
    else:
        return retrieval


def prompt_reduce(is_all, prompt: gr.Dataset, ipaddr: gr.Request):  # is_all, ipaddr: gr.Request
    """
    刷新提示词
    Args:
        is_all： prompt类型
        prompt： dataset原始对象
        ipaddr：请求用户信息
    Returns:
        返回注册函数所需的对象
    """
    tab_cls = func_box.non_personal_tag(is_all, ipaddr.client.host)
    data = prompt_retrieval(is_all=is_all, hosts=tab_cls)
    prompt['samples'] = data
    return gr.Dataset.update(samples=data, visible=True), prompt, is_all


def prompt_upload_refresh(file, prompt, pro_select, cls_name, ipaddr: gr.Request):
    """
    上传文件，将文件转换为字典，然后存储到数据库，并刷新Prompt区域
    Args:
        file： 上传的文件
        prompt： 原始prompt对象
        ipaddr：ipaddr用户请求信息
    Returns:
        注册函数所需的元祖对象
    """
    user_info = ipaddr.client.host
    if pro_select == '新建分类':
        if not cls_name:
            result = [[f'{func_box.html_tag_color("若选择新建分类，分类名不能为空", color="red")}', '']]
            prompt['samples'] = [[f'{func_box.html_tag_color("选择新建分类，分类名不能为空", color="red")}', '']]
            return gr.update(), gr.Dataset.update(samples=result, visible=True), prompt, pro_select
        tab_cls = func_box.non_personal_tag(cls_name, ipaddr.client.host)
    else:
        tab_cls = func_box.non_personal_tag(pro_select, ipaddr.client.host)
    if file.name.endswith('json'):
        upload_data = func_box.check_json_format(file.name)
    elif file.name.endswith('yaml'):
        upload_data = func_box.YamlHandle(file.name).load()
    else:
        upload_data = {}
    if upload_data != {}:
        status = SqliteHandle(f'prompt_{tab_cls}').inset_prompt(upload_data, user_info)
        ret_data = prompt_retrieval(is_all=tab_cls, hosts=tab_cls)
        return gr.Dataset.update(samples=ret_data, visible=True), prompt, tab_cls
    else:
        prompt['samples'] = [
            [f'{func_box.html_tag_color("数据解析失败，请检查文件是否符合规范", color="red")}', tab_cls]]
        return prompt['samples'], prompt, []


def prompt_delete(pro_name, prompt_dict, select_check, ipaddr: gr.Request):
    if not pro_name:
        raise gr.Error('删除的提示词名称不能为空')
    find_prompt = [i for i in prompt_dict['samples'] if i[0] == pro_name]
    if not any(find_prompt):
        raise gr.Error('无法找到提示词')
    tab_cls = func_box.non_personal_tag(select_check, ipaddr.client.host)
    sqlite_handle = SqliteHandle(table=f'prompt_{tab_cls}')
    _, source = sqlite_handle.get_prompt_value(find=pro_name)
    if not _: raise gr.Error('无法找到提示词，或请不要在所有人分类下删除提示词')
    if source in ipaddr.client.host:
        sqlite_handle.delete_prompt(pro_name)
    else:
        raise gr.Error('无法删除不属于你创建的提示词，如有紧急需求，请联系管理员')
    data = prompt_retrieval(is_all=select_check, hosts=tab_cls)
    prompt_dict['samples'] = data
    return gr.Dataset.update(samples=data, visible=True), prompt_dict


def prompt_save(txt, name, prompt: gr.Dataset, pro_select, cls_name, ipaddr: gr.Request):
    """
    编辑和保存Prompt
    Args:
        txt： Prompt正文
        name： Prompt的名字
        prompt： dataset原始对象
        ipaddr：请求用户信息
    Returns:
        返回注册函数所需的对象
    """
    user_info = ipaddr.client.host
    if pro_select == '新建分类':
        if not cls_name:
            raise gr.Error('选择新建分类，分类名不能为空')
        tab_cls = func_box.non_personal_tag(cls_name, ipaddr.client.host)
    else:
        tab_cls = func_box.non_personal_tag(pro_select, ipaddr.client.host)
    if txt and name:
        all_, personal = toolbox.get_conf('preset_prompt')[0]['key']
        if pro_select == all_:
            cls_name = personal
        elif pro_select != '新建分类':
            cls_name = pro_select
        sql_obj = SqliteHandle(f'prompt_{tab_cls}')
        cls_update = gr.Dropdown.update(value=cls_name, choices=filter_database_tables())
        _, source = sql_obj.get_prompt_value(name)
        status = sql_obj.inset_prompt({name: txt}, user_info)
        if status:
            raise gr.Error('!!!!已有其他人保存同名的prompt，请修改prompt名称后再保存')
        else:
            result = prompt_retrieval(is_all=cls_name, hosts=tab_cls)
            prompt['samples'] = result
            return "", "", cls_update, gr.Dataset.update(samples=result, visible=True), prompt
    elif not txt or not name:
        raise gr.Error('!!!!编辑框 or 名称不能为空!!!!')


def prompt_input(txt: str, prompt_str, name_str,  index, data: gr.Dataset):
    """
    点击dataset的值使用Prompt
    Args:
        txt： 输入框正文
        index： 点击的Dataset下标
        data： dataset原始对象
    Returns:
        返回注册函数所需的对象
    """
    data_str = str(data['samples'][index][1])
    data_name = str(data['samples'][index][0])
    rp_str = '{{{v}}}'
    def str_v_handle(__str):
        temp_ = data_str
        if temp_.find(rp_str) != -1 and __str:
            txt_temp = temp_.replace(rp_str, __str)
        else:
            txt_temp = temp_ + txt
        return txt_temp
    new_txt = str_v_handle(txt)
    if prompt_str != '' or name_str != '':
        data_str, data_name = prompt_str, name_str
    return new_txt, data_str, data_name


def show_prompt_result(index, data: gr.Dataset, chatbot, pro_edit, pro_name):
    """
    查看Prompt的对话记录结果
    Args:
        index： 点击的Dataset下标
        data： dataset原始对象
        chatbot：聊天机器人
    Returns:
        返回注册函数所需的对象
    """
    click = data['samples'][index]
    if func_box.str_is_list(click[2]):
        list_copy = eval(click[2])
        for i in range(0, len(list_copy), 2):
            if i + 1 >= len(list_copy):  # 如果下标越界了，单独处理最后一个元素
                chatbot.append([list_copy[i]])
            else:
                chatbot.append([list_copy[i], list_copy[i + 1]])
            yield chatbot, pro_edit, pro_name, gr.Accordion.update()
    elif click[2] is None:
        pro_edit = click[1]
        pro_name = click[3]
        chatbot.append([click[3], click[1]])
    yield chatbot, pro_edit, pro_name, gr.Accordion.update(open=True)


# TODO < -------------------------------- 搜索函数注册区 -------------------------------->
def diff_list(txt='', percent=0.70, switch: list = None, lst: dict = None, sp=15, hosts=''):
    """
    按照搜索结果统计相似度的文本，两组文本相似度>70%的将统计在一起，取最长的作为key
    Args:
        txt (str): 过滤文本
        percent (int): TF系数，用于计算文本相似度
        switch (list): 过滤个人或所有人的Prompt
        lst：指定一个列表或字典
        sp: 截取展示的文本长度
        hosts : 请求人的ip
    Returns:
        返回一个列表
    """
    is_all = toolbox.get_conf('preset_prompt')[0]['value']
    count_dict = {}
    if not lst:
        lst = {}
        tabs = SqliteHandle().get_tables()
        if is_all in switch:
            data, source = SqliteHandle(f"ai_common_{hosts}").get_prompt_value(txt)
            lst.update(data)
        else:
            for tab in tabs:
                if tab.startswith('ai_common'):
                    data, source = SqliteHandle(f"{tab}").get_prompt_value(txt)
                    lst.update(data)
        data, source = SqliteHandle(f"ai_private_{hosts}").get_prompt_value(txt)
        lst.update(data)
    # diff 数据，根据precent系数归类数据
    str_ = time.time()
    def tf_factor_calcul(i):
        found = False
        dict_copy = count_dict.copy()
        for key in dict_copy.keys():
            str_tf = Levenshtein.jaro_winkler(i, key)
            if str_tf >= percent:
                if len(i) > len(key):
                    count_dict[i] = count_dict.copy()[key] + 1
                    count_dict.pop(key)
                else:
                    count_dict[key] += 1
                found = True
                break
        if not found: count_dict[i] = 1

    with ThreadPoolExecutor(100) as executor:
        executor.map(tf_factor_calcul, lst)
    print('计算耗时', time.time() - str_)
    sorted_dict = sorted(count_dict.items(), key=lambda x: x[1], reverse=True)
    if switch:
        sorted_dict += prompt_retrieval(is_all=switch, hosts=hosts, search=True)
    dateset_list = []
    for key in sorted_dict:
        # 开始匹配关键字
        index = str(key[0]).lower().find(txt.lower())
        index_ = str(key[1]).lower().find(txt.lower())
        if index != -1 or index_ != -1:
            if index == -1: index = index_  # 增加搜索prompt 名称
            # sp=split 用于判断在哪里启动、在哪里断开
            if index - sp > 0:
                start = index - sp
            else:
                start = 0
            if len(key[0]) > sp * 2:
                end = key[0][-sp:]
            else:
                end = ''
            # 判断有没有传需要匹配的字符串，有则筛选、无则全返
            if txt == '' and len(key[0]) >= sp:
                show = key[0][0:sp] + " . . . " + end
                show = show.replace('<', '')
            elif txt == '' and len(key[0]) < sp:
                show = key[0][0:sp]
                show = show.replace('<', '')
            else:
                show = str(key[0][start:index + sp]).replace('<', '').replace(txt, func_box.html_tag_color(txt))
            show += f"  {func_box.html_tag_color(' X ' + str(key[1]))}"
            if lst.get(key[0]):
                be_value = lst[key[0]]
            else:
                be_value = None
            value = be_value
            dateset_list.append([show, key[0], value, key[1]])
    return dateset_list


def reuse_chat(result, chatbot, history, say):
    """复用对话记录"""
    if result is None or result == []:
        return chatbot, history, gr.update(), gr.update()
    else:
        chatbot += result
        history += [func_box.pattern_html(_) for i in result for _ in i]
        return chatbot, history, say


def draw_results(txt, prompt: dict, percent, switch, ipaddr: gr.Request):
    """
    绘制搜索结果
    Args:
        txt (str): 过滤文本
        prompt : 原始的dataset对象
        percent (int): TF系数，用于计算文本相似度
        switch (list): 过滤个人或所有人的Prompt
        ipaddr : 请求人信息
    Returns:
        注册函数所需的元祖对象
    """
    data = diff_list(txt, percent=percent, switch=switch, hosts=ipaddr.client.host)
    prompt['samples'] = data
    return gr.Dataset.update(samples=data, visible=True), prompt


# TODO < -------------------------------- 页面刷新函数注册区 -------------------------------->
def mobile_access(request: gr.Request): # 为适配手机端
    user_agent = request.kwargs['headers']['user-agent'].lower()
    if user_agent.find('android') != -1 or user_agent.find('iphone') != -1:
        return gr.Column.update(visible=False), gr.Dropdown.update(show_label=False)
    else:
        return gr.update(), gr.update()


def refresh_load_data(prompt, request: gr.Request):
    """
    Args:
        prompt: prompt dataset组件
    Returns:
        预期是每次刷新页面，加载最新数据
    """
    is_all = toolbox.get_conf('preset_prompt')[0]['value']
    data = prompt_retrieval(is_all=is_all)
    prompt['samples'] = data
    know_list = ['新建分类'] + os.listdir(func_box.knowledge_path)
    load_list, user_list = func_box.get_directory_list(os.path.join(func_box.knowledge_path, '公共知识库'),
                                                       request.client.host)
    know_cls = gr.Dropdown.update(choices=know_list, value='公共知识库')
    know_load = gr.Dropdown.update(choices=load_list, label='公共知识库', show_label=True)
    know_user = gr.Dropdown.update(choices=user_list)
    select_list = filter_database_tables()
    outputs = [gr.Dataset.update(samples=data, visible=True), prompt, gr.Dropdown.update(choices=select_list),
                know_cls, know_user, know_load]
    return outputs


def refresh_user_data(cookies, ipaddr: gr.Request):
    user_path = os.path.join(func_box.history_path, ipaddr.client.host)
    file_list, only_name, new_path, new_name = func_box.get_files_list(user_path, filter_format=['.json'])
    history_handle = func_box.HistoryJsonHandle(new_path)
    history_update_combo = history_handle.update_for_history(cookies, new_name)
    outputs = [gr.Radio.update(choices=only_name, value=new_name, visible=True), *history_update_combo,
               new_name]
    return outputs