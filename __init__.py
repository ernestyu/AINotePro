"""
AINotePro - Anki plugin
Author: Ernest
Version: 1.0
Description: An Anki plugin with multi-tab AI configuration dialog.
"""

from aqt import mw, gui_hooks
from aqt.qt import QAction, qconnect
from aqt.browser import Browser
from aqt.utils import showInfo
from .ainotepro.ainotepro_gui import show_ainotepro_dialog
from .ainotepro.remove import RemoveDialog

def open_ainotepro_config_in_browser(browser: Browser):
    """弹出 AINotePro 多标签配置界面"""
    if not browser:
        showInfo("Please open the browser first.")
        return
    show_ainotepro_dialog(browser)

def open_remove_dialog(browser: Browser):
    """弹出 Remove Field Content 窗口"""
    if not browser:
        showInfo("Please open the browser first.")
        return
    dialog = RemoveDialog(parent=None, browser=browser)
    dialog.exec()

def add_browser_menu(browser: Browser, remove_context=None):
    """
    在 Anki 浏览器菜单中添加一个顶级菜单 'AiNotePro'，
    其中包含打开设置对话框的入口。
    """

    menu_name = "AINotePro"

    # 判断是否已存在同名菜单，避免重复创建
    for child in browser.form.menubar.actions():
        if child.text() == menu_name:
            # 如果已经创建过，则不再重复添加
            return

    # 创建 AiNotePro 顶级菜单
    ainotepro_menu = browser.form.menubar.addMenu(menu_name)

    # 添加一个动作：Open Settings
    action_settings = QAction("Add Context to selected Field...", browser)
    qconnect(action_settings.triggered, lambda _, b=browser: open_ainotepro_config_in_browser(b))
    ainotepro_menu.addAction(action_settings)

    # 添加“移除扩展内容”
    action_remove = QAction("Remove Context from selected Field...", browser)
    qconnect(action_remove.triggered, lambda _, b=browser: open_remove_dialog(b))
    ainotepro_menu.addAction(action_remove)


@gui_hooks.browser_will_show.append
def on_browser_will_show(browser: Browser):
    """
    当浏览器窗口即将显示时，调用 add_browser_menu 来添加菜单。
    """
    try:
        add_browser_menu(browser)
    except Exception as e:
        print(f"Error adding AiNotePro menu: {e}")
