#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Send a WeChat message to a friend using ItChat.

Usage:
  python src/send_message.py --to "刘敏" --text "你好"
"""
import argparse
import os
import sys
import itchat

DEFAULT_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
DEFAULT_LOGIN_FILE = os.path.join(DEFAULT_STORAGE_DIR, "itchat.pkl")


def ensure_storage_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def login(hot_reload: bool = True) -> None:
    ensure_storage_dir(DEFAULT_STORAGE_DIR)
    itchat.auto_login(
        hotReload=hot_reload,
        statusStorageDir=DEFAULT_LOGIN_FILE,
        enableCmdQR=False,
    )


def find_friend(name: str):
    # Try exact match by remark/nickname/wechat account
    results = itchat.search_friends(name=name)
    if results:
        return results[0]
    # Try nickname
    results = itchat.search_friends(nickName=name)
    if results:
        return results[0]
    # Try remark name
    results = itchat.search_friends(remarkName=name)
    if results:
        return results[0]
    return None


def send_text(to_name: str, text: str) -> None:
    friend = find_friend(to_name)
    if not friend:
        print(f"未找到联系人: {to_name}")
        sys.exit(2)
    itchat.send(text, toUserName=friend['UserName'])
    print(f"已发送给 {friend.get('NickName') or to_name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="好友昵称/备注/微信号")
    parser.add_argument("--text", required=True, help="发送文本内容")
    parser.add_argument("--no-hot-reload", action="store_true", help="禁用热重载登录态")
    args = parser.parse_args()

    login(hot_reload=not args.no_hot_reload)
    send_text(args.to, args.text)


if __name__ == "__main__":
    main()
