# -*- coding: utf-8 -*-
# polymarket_v1.0.0
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
import json
import threading
import time
import os
import logging
from datetime import datetime
import re
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pyautogui
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import socket
import sys
import subprocess


class Logger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 创建logs目录（如果不存在）
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        # 设置日志文件名（使用当前日期）
        log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}.log"
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # 创建格式器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message):
        self.logger.debug(message)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def critical(self, message):
        self.logger.critical(message)


class CryptoTrader:
    def __init__(self):
        super().__init__()
        self.logger = Logger('crypto_trader')
        self.driver = None
        self.running = False
        self.retry_count = 3
        self.retry_interval = 5
        # 添加交易次数计数器
        self.trade_count = 0
        self.is_trading = False  # 添加交易状态标志
        self.refresh_interval = 300000  # 5分钟 = 300000毫秒
        self.refresh_timer = None  # 用于存储定时器ID
        
        try:
            self.config = self.load_config()
            self.setup_gui()
            
            # 获取屏幕尺寸并设置窗口位置
            self.root.update_idletasks()  # 确保窗口尺寸已计算
            window_width = self.root.winfo_width()
            screen_height = self.root.winfo_screenheight()
            
            # 设置窗口位置在屏幕最左边
            self.root.geometry(f"{window_width}x{screen_height}+0+0")
        except Exception as e:
            self.logger.error(f"初始化失败: {str(e)}")
            messagebox.showerror("错误", "程序初始化失败，请检查日志文件")
            sys.exit(1)
        
        # 检查是否是重启
        import sys
        self.is_restart = '--restart' in sys.argv
        
        # 如果是重启,延迟2秒后自动点击开始监控
        if self.is_restart:
            self.root.after(2000, self.auto_start_monitor)

        # 添加当前监控网址的属性
        self.current_url = ''
        
        # 添加URL监控定时器
        self.url_check_timer = None
        
        # 添加登录状态监控定时器
        self.login_check_timer = None

    def load_config(self):
        try:
            # 确认配置
            default_config = {
                'website': {
                    'url': ''
                },
                'trading': {
                    'Yes0': {'target_price': 0.53, 'amount': 0.0},
                    'Yes1': {'target_price': 0.00, 'amount': 0.0},
                    'Yes2': {'target_price': 0.00, 'amount': 0.0},
                    'Yes3': {'target_price': 0.00, 'amount': 0.0},
                    'Yes4': {'target_price': 0.00, 'amount': 0.0},
                    'Yes5': {'target_price': 0.00, 'amount': 0.0},
                    'No0': {'target_price': 0.53, 'amount': 0.0},
                    'No1': {'target_price': 0.00, 'amount': 0.0},
                    'No2': {'target_price': 0.00, 'amount': 0.0},
                    'No3': {'target_price': 0.00, 'amount': 0.0},
                    'No4': {'target_price': 0.00, 'amount': 0.0},
                    'No5': {'target_price': 0.00, 'amount': 0.0}
                }
            }

            try:
                # 尝试读取现有配置
                with open('config.json', 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.logger.info("成功加载配置文件")
                    
                    # 合并保存的配置和默认配置
                    for key in default_config:
                        if key not in saved_config:
                            saved_config[key] = default_config[key]
                        elif isinstance(default_config[key], dict):
                            for sub_key in default_config[key]:
                                if sub_key not in saved_config[key]:
                                    saved_config[key][sub_key] = default_config[key][sub_key]
                    return saved_config       
            except FileNotFoundError:
                self.logger.warning("配置文件不存在，创建默认配置")
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4)
                return default_config
            except json.JSONDecodeError:
                self.logger.error("配置文件格式错误，使用默认配置")
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4)
                return default_config
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {str(e)}")
            raise

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Polymarket自动交易")
        # 创建主滚动框架
        main_canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        # 配置滚动区域
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        # 在 Canvas 中创建窗口
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        # 简化的滚动事件处理
        def _on_mousewheel(event):
            try:
                if platform.system() == 'Linux':
                    if event.num == 4:
                        main_canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        main_canvas.yview_scroll(1, "units")
                elif platform.system() == 'Darwin':
                    main_canvas.yview_scroll(-int(event.delta), "units")
                else:  # Windows
                    main_canvas.yview_scroll(-int(event.delta/120), "units")
            except Exception as e:
                self.logger.error(f"滚动事件处理错误: {str(e)}")
        # 绑定滚动事件
        if platform.system() == 'Linux':
            main_canvas.bind_all("<Button-4>", _on_mousewheel)
            main_canvas.bind_all("<Button-5>", _on_mousewheel)
        else:
            main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # 添加简化的键盘滚动支持
        def _on_arrow_key(event):
            try:
                if event.keysym == 'Up':
                    main_canvas.yview_scroll(-1, "units")
                elif event.keysym == 'Down':
                    main_canvas.yview_scroll(1, "units")
            except Exception as e:
                self.logger.error(f"键盘滚动事件处理错误: {str(e)}")
        # 绑定方向键
        main_canvas.bind_all("<Up>", _on_arrow_key)
        main_canvas.bind_all("<Down>", _on_arrow_key)
        
        # 放置滚动组件
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 金额设置框架
        amount_settings_frame = ttk.LabelFrame(scrollable_frame, text="金额设置", padding=(5, 5))
        amount_settings_frame.pack(fill="x", padx=5, pady=5)
        
        # 创建金额设置容器的内部框架
        settings_container = ttk.Frame(amount_settings_frame)
        settings_container.pack(expand=True)
        
        # 初始金额设置
        ttk.Label(settings_container, text="初始金额(%):").grid(row=0, column=0, padx=5, pady=5)
        self.initial_amount_entry = ttk.Entry(settings_container, width=10)
        self.initial_amount_entry.insert(0, "6.6")
        self.initial_amount_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # 反水一次设置
        ttk.Label(settings_container, text="反水一次(%):").grid(row=0, column=2, padx=5, pady=5)
        self.first_rebound_entry = ttk.Entry(settings_container, width=10)
        self.first_rebound_entry.insert(0, "214")
        self.first_rebound_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # 反水N次设置
        ttk.Label(settings_container, text="反水N次(%):").grid(row=0, column=4, padx=5, pady=5)
        self.n_rebound_entry = ttk.Entry(settings_container, width=10)
        self.n_rebound_entry.insert(0, "113")
        self.n_rebound_entry.grid(row=0, column=5, padx=5, pady=5)
        
        # 配置列权重使输入框均匀分布
        for i in range(6):
            settings_container.grid_columnconfigure(i, weight=1)
        # 设置窗口大小和位置
        window_width = 800
        window_height = 600
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f'{window_width}x{window_height}+{x}+{y}')
        
        # 监控网站配置
        url_frame = ttk.LabelFrame(scrollable_frame, text="监控网站配置", padding=(5, 2))
        url_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(url_frame, text="网站地址:", font=('Arial', 10)).grid(row=0, column=0, padx=5, pady=5)
        
        # 创建下拉列和输入框组合控件
        self.url_entry = ttk.Combobox(url_frame, width=72)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # 从配置文件加载历史记录
        if 'url_history' not in self.config:
            self.config['url_history'] = []
        self.url_entry['values'] = self.config['url_history']
        
        # 如果有当前URL，设置为默认值
        current_url = self.config.get('website', {}).get('url', '')
        if current_url:
            self.url_entry.set(current_url)
        
        # 在创建按钮之前，添加自定义样式
        style = ttk.Style()
        style.configure('Black.TButton', foreground='blue')  # 默认蓝色文字
        style.configure('Red.TButton', foreground='red')  # 保留红色样式用于状态变化
        
        # 控制按钮区域
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill="x", padx=5, pady=5)
        
        # 开始和停止按钮
        self.start_button = ttk.Button(button_frame, text="开始监控", 
                                          command=self.start_monitoring, width=10,
                                          style='Black.TButton')  # 默认使用黑色文字
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="停止监控", 
                                     command=self.stop_monitoring, width=10,
                                     style='Black.TButton')  # 默认使用黑色文字
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button['state'] = 'disabled'
        
        # 更新下单金额按钮
        self.update_amount_button = ttk.Button(button_frame, text="更新下单金额", 
                                             command=self.set_yes_no_cash, width=10,
                                             style='Black.TButton')  # 默认使用黑色文字
        self.update_amount_button.pack(side=tk.LEFT, padx=5)
        self.update_amount_button['state'] = 'disabled'  # 初始禁用
        
        # 交易币对显示区域
        pair_frame = ttk.Frame(scrollable_frame)
        pair_frame.pack(fill="x", padx=10, pady=5)
        
        # 添加交易币对显示区域
        pair_container = ttk.Frame(pair_frame)
        pair_container.pack(anchor="center")
        
        # 交易币种及日期，颜色为蓝色
        ttk.Label(pair_container, text="交易币种及日期:", 
                 font=('Arial', 16), foreground='blue').pack(side=tk.LEFT, padx=5)
        self.trading_pair_label = ttk.Label(pair_container, text="--", 
                                        font=('Arial', 16, 'bold'), foreground='blue')
        self.trading_pair_label.pack(side=tk.LEFT, padx=5)
        
        # 修改实时价格显示区域
        price_frame = ttk.LabelFrame(scrollable_frame, text="实时价格", padding=(5, 5))
        price_frame.pack(padx=5, pady=5, fill="x")
        
        # 创建一个框架来水平排列所有价格信息
        prices_container = ttk.Frame(price_frame)
        prices_container.pack(expand=True)  # 添加expand=True使容器居中
        
        # Yes价格显示
        self.yes_price_label = ttk.Label(prices_container, text="Yes: 等待数据...", 
                                        font=('Arial', 20), foreground='red')
        self.yes_price_label.pack(side=tk.LEFT, padx=20)
        
        # No价格显示
        self.no_price_label = ttk.Label(prices_container, text="No: 等待数据...", 
                                       font=('Arial', 20), foreground='red')
        self.no_price_label.pack(side=tk.LEFT, padx=20)
        
        # 最后更新时间 - 靠右下对齐
        self.last_update_label = ttk.Label(price_frame, text="最后更新: --", 
                                          font=('Arial', 2))
        self.last_update_label.pack(side=tk.LEFT, anchor='se', padx=5)
        
        # 修改实时资金显示区域
        balance_frame = ttk.LabelFrame(scrollable_frame, text="实时资金", padding=(5, 5))
        balance_frame.pack(padx=5, pady=5, fill="x")
        
        # 创建一个框架来水平排列所有资金信息
        balance_container = ttk.Frame(balance_frame)
        balance_container.pack(expand=True)  # 添加expand=True使容器居中
        
        # Portfolio显示
        self.portfolio_label = ttk.Label(balance_container, text="Portfolio: 等待数据...", 
                                        font=('Arial', 16), foreground='#9370DB') # 修改为绿色
        self.portfolio_label.pack(side=tk.LEFT, padx=20)
        
        # Cash显示
        self.cash_label = ttk.Label(balance_container, text="Cash: 等待数据...", 
                                   font=('Arial', 16), foreground='#9370DB') # 修改为绿色
        self.cash_label.pack(side=tk.LEFT, padx=20)
        
        # 最后更新时间 - 靠右下对齐
        self.balance_update_label = ttk.Label(balance_frame, text="最后更新: --", 
                                           font=('Arial', 2))
        self.balance_update_label.pack(side=tk.LEFT, anchor='se', padx=5)
        
        # 创建Yes/No
        config_frame = ttk.Frame(scrollable_frame)
        config_frame.pack(fill="x", padx=5, pady=5)
        
        # 左右分栏显示Yes/No配置
        self.yes_frame = ttk.LabelFrame(config_frame, text="Yes配置", padding=(5, 5))
        self.yes_frame.grid(row=0, column=0, padx=5, sticky="ew")
        config_frame.grid_columnconfigure(0, weight=1)
        
        ttk.Label(self.yes_frame, text="Yes 0 价格($):", font=('Arial', 12)).grid(row=0, column=0, padx=5, pady=5)
        self.yes_price_entry = ttk.Entry(self.yes_frame)
        self.yes_price_entry.insert(0, str(self.config['trading']['Yes0']['target_price']))
        self.yes_price_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(self.yes_frame, text="Yes 0 金额:", font=('Arial', 12)).grid(row=1, column=0, padx=5, pady=5)
        self.yes_amount_entry = ttk.Entry(self.yes_frame)
        self.yes_amount_entry.insert(0, str(self.config['trading']['Yes0']['amount']))
        self.yes_amount_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # 直接创建所有Yes Entry对象并设置默认值
        self.yes1_price_entry = ttk.Entry(self.yes_frame)
        self.yes1_price_entry.insert(0, "0.00")
        self.yes2_price_entry = ttk.Entry(self.yes_frame)
        self.yes2_price_entry.insert(0, "0.00")
        self.yes3_price_entry = ttk.Entry(self.yes_frame)
        self.yes3_price_entry.insert(0, "0.00")
        self.yes4_price_entry = ttk.Entry(self.yes_frame)
        self.yes4_price_entry.insert(0, "0.00")
        self.yes5_price_entry = ttk.Entry(self.yes_frame)
        self.yes5_price_entry.insert(0, "0.00")
        # 设置它们的grid布局
        self.yes1_price_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.yes2_price_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        self.yes3_price_entry.grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        self.yes4_price_entry.grid(row=8, column=1, padx=5, pady=5, sticky="ew")
        self.yes5_price_entry.grid(row=10, column=1, padx=5, pady=5, sticky="ew")
        
        # 修改Yes1-5和No1-5的默认价格值
        for i in range(4):
            ttk.Label(self.yes_frame, text=f"Yes {i+1} 价格($):", font=('Arial', 12)).grid(row=i*2+2, column=0, padx=5, pady=5)
            # 设置默认价格为0.00
            getattr(self, f'yes{i+1}_price_entry').delete(0, tk.END)
            getattr(self, f'yes{i+1}_price_entry').insert(0, "0.00")
            
            ttk.Label(self.yes_frame, text=f"Yes {i+1} 金额:", font=('Arial', 12)).grid(row=i*2+3, column=0, padx=5, pady=5)
            amount_entry = ttk.Entry(self.yes_frame)
            amount_entry.insert(0, "0.0")
            amount_entry.grid(row=i*2+3, column=1, padx=5, pady=5, sticky="ew")
        
        # Yes 5 配置
        ttk.Label(self.yes_frame, text="Yes 5 价格($):", font=('Arial', 12)).grid(row=10, column=0, padx=5, pady=5)
        price_entry = ttk.Entry(self.yes_frame)
        price_entry.insert(0, "0.00")  # 修改为0.00
        price_entry.grid(row=10, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(self.yes_frame, text="Yes 5 金额:", font=('Arial', 12)).grid(row=11, column=0, padx=5, pady=5)
        amount_entry = ttk.Entry(self.yes_frame)
        amount_entry.insert(0, "0.0")
        amount_entry.grid(row=11, column=1, padx=5, pady=5, sticky="ew")
        
        # Yes 6 配置
        ttk.Label(self.yes_frame, text="Yes 6 价格($):", font=('Arial', 14), foreground='red').grid(row=12, column=0, padx=5, pady=5)
        price_entry = ttk.Entry(self.yes_frame)
        price_entry.insert(0, "0.00")  # 修改默认值为0.00
        price_entry.grid(row=12, column=1, padx=5, pady=5, sticky="ew")

        # No 配置区域
        self.no_frame = ttk.LabelFrame(config_frame, text="No配置", padding=(10, 5))
        self.no_frame.grid(row=0, column=1, padx=5, sticky="ew")
        config_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(self.no_frame, text="No 0 价格($):", font=('Arial', 12)).grid(row=0, column=0, padx=5, pady=5)
        self.no_price_entry = ttk.Entry(self.no_frame)
        self.no_price_entry.insert(0, str(self.config['trading']['No0']['target_price']))
        self.no_price_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(self.no_frame, text="No 0 金额:", font=('Arial', 12)).grid(row=1, column=0, padx=5, pady=5)
        self.no_amount_entry = ttk.Entry(self.no_frame)
        self.no_amount_entry.insert(0, str(self.config['trading']['No0']['amount']))
        self.no_amount_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # 直接创建所有No Entry对象并设置默认值
        self.no1_price_entry = ttk.Entry(self.no_frame)
        self.no1_price_entry.insert(0, "0.00")
        self.no2_price_entry = ttk.Entry(self.no_frame)
        self.no2_price_entry.insert(0, "0.00")
        self.no3_price_entry = ttk.Entry(self.no_frame)
        self.no3_price_entry.insert(0, "0.00")
        self.no4_price_entry = ttk.Entry(self.no_frame)
        self.no4_price_entry.insert(0, "0.00")
        self.no5_price_entry = ttk.Entry(self.no_frame)
        self.no5_price_entry.insert(0, "0.00")
    
        # 设置它们的grid布局
        self.no1_price_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.no2_price_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        self.no3_price_entry.grid(row=6, column=1, padx=5, pady=5, sticky="ew")
        self.no4_price_entry.grid(row=8, column=1, padx=5, pady=5, sticky="ew")
        self.no5_price_entry.grid(row=10, column=1, padx=5, pady=5, sticky="ew")
        
        for i in range(4):
            ttk.Label(self.no_frame, text=f"No {i+1} 价格($):", font=('Arial', 12)).grid(row=i*2+2, column=0, padx=5, pady=5)
            ttk.Label(self.no_frame, text=f"No {i+1} 金额:", font=('Arial', 12)).grid(row=i*2+3, column=0, padx=5, pady=5)
            # 设置默认价格为0.00
            getattr(self, f'no{i+1}_price_entry').delete(0, tk.END)
            getattr(self, f'no{i+1}_price_entry').insert(0, "0.00")
            
            ttk.Label(self.no_frame, text=f"No {i+1} 金额:", font=('Arial', 12)).grid(row=i*2+3, column=0, padx=5, pady=5)
            amount_entry = ttk.Entry(self.no_frame)
            amount_entry.insert(0, "0.0")
            amount_entry.grid(row=i*2+3, column=1, padx=5, pady=5, sticky="ew")
        
        # No 5 配置
        ttk.Label(self.no_frame, text="No 5 价格($):", font=('Arial', 12)).grid(row=10, column=0, padx=5, pady=5)
        price_entry = ttk.Entry(self.no_frame)
        price_entry.insert(0, "0.00")  # 修改为0.00
        price_entry.grid(row=10, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(self.no_frame, text="No 5 金额:", font=('Arial', 12)).grid(row=11, column=0, padx=5, pady=5)
        amount_entry = ttk.Entry(self.no_frame)
        amount_entry.insert(0, "0.0")
        amount_entry.grid(row=11, column=1, padx=5, pady=5, sticky="ew")
        
        # No 6 配置
        ttk.Label(self.no_frame, text="No 6 价格($):", font=('Arial', 14), foreground='red').grid(row=12, column=0, padx=5, pady=5)
        price_entry = ttk.Entry(self.no_frame)
        price_entry.insert(0, "0.00")  # 修改默认值为0.00
        price_entry.grid(row=12, column=1, padx=5, pady=5, sticky="ew")

        # 修改买入按钮区域
        buy_frame = ttk.LabelFrame(scrollable_frame, text="买入按钮", padding=(5, 5))
        buy_frame.pack(fill="x", padx=5, pady=5)

        # 创建按钮框架
        buy_button_frame = ttk.Frame(buy_frame)
        buy_button_frame.pack(expand=True)  # 添加expand=True使容器居中

        # 第一行按钮
        self.buy_button = ttk.Button(buy_button_frame, text="Buy", width=15,
                                    command=self.click_buy)
        self.buy_button.grid(row=0, column=0, padx=5, pady=5)

        self.buy_yes_button = ttk.Button(buy_button_frame, text="Buy-Yes", width=15,
                                        command=self.click_buy_yes)
        self.buy_yes_button.grid(row=0, column=1, padx=5, pady=5)

        self.buy_no_button = ttk.Button(buy_button_frame, text="Buy-No", width=15,
                                       command=self.click_buy_no)
        self.buy_no_button.grid(row=0, column=2, padx=5, pady=5)

        self.buy_confirm_button = ttk.Button(buy_button_frame, text="Buy-买入", width=15,
                                            command=lambda: self.click_website_button("Buy-Confirm"))
        self.buy_confirm_button.grid(row=0, column=3, padx=5, pady=5)

        # 第二行按钮
        self.amount_button = ttk.Button(buy_button_frame, text="Amount-Yes0", width=15)
        self.amount_button.bind('<Button-1>', self.click_amount)
        self.amount_button.grid(row=1, column=0, padx=5, pady=5)

        self.amount_yes1_button = ttk.Button(buy_button_frame, text="Amount-Yes1", width=15)
        self.amount_yes1_button.bind('<Button-1>', self.click_amount)
        self.amount_yes1_button.grid(row=1, column=1, padx=5, pady=5)

        self.amount_yes2_button = ttk.Button(buy_button_frame, text="Amount-Yes2", width=15)
        self.amount_yes2_button.bind('<Button-1>', self.click_amount)
        self.amount_yes2_button.grid(row=1, column=2, padx=5, pady=5)

        self.amount_yes3_button = ttk.Button(buy_button_frame, text="Amount-Yes3", width=15)
        self.amount_yes3_button.bind('<Button-1>', self.click_amount)
        self.amount_yes3_button.grid(row=1, column=3, padx=5, pady=5)

        # 第三行按钮
        self.amount_yes4_button = ttk.Button(buy_button_frame, text="Amount-Yes4", width=15)
        self.amount_yes4_button.bind('<Button-1>', self.click_amount)
        self.amount_yes4_button.grid(row=2, column=0, padx=5, pady=5)

        self.amount_yes5_button = ttk.Button(buy_button_frame, text="Amount-Yes5", width=15)
        self.amount_yes5_button.bind('<Button-1>', self.click_amount)
        self.amount_yes5_button.grid(row=2, column=1, padx=5, pady=5)

        self.amount_no0_button = ttk.Button(buy_button_frame, text="Amount-No0", width=15)
        self.amount_no0_button.bind('<Button-1>', self.click_amount)
        self.amount_no0_button.grid(row=2, column=2, padx=5, pady=5)

        self.amount_no1_button = ttk.Button(buy_button_frame, text="Amount-No1", width=15)
        self.amount_no1_button.bind('<Button-1>', self.click_amount)
        self.amount_no1_button.grid(row=2, column=3, padx=5, pady=5)

        # 第四行按钮
        self.amount_no2_button = ttk.Button(buy_button_frame, text="Amount-No2", width=15)
        self.amount_no2_button.bind('<Button-1>', self.click_amount)
        self.amount_no2_button.grid(row=3, column=0, padx=5, pady=5)

        self.amount_no3_button = ttk.Button(buy_button_frame, text="Amount-No3", width=15)
        self.amount_no3_button.bind('<Button-1>', self.click_amount)
        self.amount_no3_button.grid(row=3, column=1, padx=5, pady=5)

        self.amount_no4_button = ttk.Button(buy_button_frame, text="Amount-No4", width=15)
        self.amount_no4_button.bind('<Button-1>', self.click_amount)
        self.amount_no4_button.grid(row=3, column=2, padx=5, pady=5)

        self.amount_no5_button = ttk.Button(buy_button_frame, text="Amount-No5", width=15)
        self.amount_no5_button.bind('<Button-1>', self.click_amount)
        self.amount_no5_button.grid(row=3, column=3, padx=5, pady=5)

        # 配置列权重使按钮均匀分布
        for i in range(4):
            buy_button_frame.grid_columnconfigure(i, weight=1)

        # 修改卖出按钮区域
        sell_frame = ttk.LabelFrame(scrollable_frame, text="卖出按钮", padding=(10, 5))
        sell_frame.pack(fill="x", padx=10, pady=5)

        # 创建按钮框架
        button_frame = ttk.Frame(sell_frame)
        button_frame.pack(expand=True)  # 添加expand=True使容器居

        # 第一行按钮
        self.position_sell_yes_button = ttk.Button(button_frame, text="Positions-Sell-Yes", width=15,
                                                 command=self.click_position_sell)
        self.position_sell_yes_button.grid(row=0, column=0, padx=5, pady=5)

        self.position_sell_no_button = ttk.Button(button_frame, text="Positions-Sell-No", width=15,
                                                command=self.click_position_sell_no)
        self.position_sell_no_button.grid(row=0, column=1, padx=5, pady=5)

        self.sell_profit_button = ttk.Button(button_frame, text="Sell-卖出", width=15,
                                           command=self.click_profit_sell)
        self.sell_profit_button.grid(row=0, column=2, padx=5, pady=5)

        self.sell_button = ttk.Button(button_frame, text="Sell", width=15,
                                    command=self.click_sell)
        self.sell_button.grid(row=0, column=3, padx=5, pady=5)

        # 第二行按钮
        self.sell_yes_button = ttk.Button(button_frame, text="Sell-Yes", width=15,
                                        command=self.click_sell_yes)
        self.sell_yes_button.grid(row=1, column=0, padx=5, pady=5)

        self.sell_no_button = ttk.Button(button_frame, text="Sell-No", width=15,
                                       command=self.click_sell_no)
        self.sell_no_button.grid(row=1, column=1, padx=5, pady=5)

        # 配置列权重使按钮均匀分布
        for i in range(4):
            button_frame.grid_columnconfigure(i, weight=1)

        # 添加状态标签 (在卖出按钮区域之后)
        self.status_label = ttk.Label(scrollable_frame, text="状态: 未运行", 
                                     font=('Arial', 10, 'bold'))
        self.status_label.pack(pady=5)
        
        # 添加版权信息标签
        copyright_label = ttk.Label(scrollable_frame, text="Powered by 无为 Copyright 2024",
                                   font=('Arial', 12), foreground='gray')
        copyright_label.pack(pady=(0, 5))  # 上边距0，下距5

    def set_yes_no_cash(self):
        """设置 Yes/No 各级金额"""
        try:
            #设置重试参数
            max_retry = 30
            retry_count = 0
            cash_value = None

            while retry_count < max_retry:
                try:
                    # 获取 Cash 值
                    cash_text = self.cash_label.cget("text") 
                    # 使用正则表达式提取数字
                    cash_match = re.search(r'\$?([\d,]+\.?\d*)', cash_text)
                    if not cash_match:
                        raise ValueError("无法从Cash值中提取数字")
                    # 移除逗号并转换为浮点数
                    cash_value = float(cash_match.group(1).replace(',', ''))
                    self.logger.info(f"提取到Cash值: {cash_value}")
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retry:
                        time.sleep(2)
                    else:
                        raise ValueError("获取Cash值失败")
            # 获取金额设置中的百分比值
            initial_percent = float(self.initial_amount_entry.get()) / 100  # 初始金额百分比
            first_rebound_percent = float(self.first_rebound_entry.get()) / 100  # 反水一次百分比
            n_rebound_percent = float(self.n_rebound_entry.get()) / 100  # 反水N次百分比
            
            # 计算基础金额
            base_amount = cash_value * initial_percent
            
            # 设置 Yes0 和 No0
            self.yes_amount_entry.delete(0, tk.END)
            self.yes_amount_entry.insert(0, f"{base_amount:.2f}")
            self.no_amount_entry.delete(0, tk.END)
            self.no_amount_entry.insert(0, f"{base_amount:.2f}")
            
            # 计算并设置 Yes1/No1
            yes1_amount = base_amount * first_rebound_percent
            yes1_entry = self.yes_frame.grid_slaves(row=3, column=1)[0]
            yes1_entry.delete(0, tk.END)
            yes1_entry.insert(0, f"{yes1_amount:.2f}")
            
            no1_entry = self.no_frame.grid_slaves(row=3, column=1)[0]
            no1_entry.delete(0, tk.END)
            no1_entry.insert(0, f"{yes1_amount:.2f}")
            
            # 计算并设置 Yes2-5/No2-5 (每级是上一级的n_rebound_percent)
            prev_yes_amount = yes1_amount
            prev_no_amount = yes1_amount
            for i in range(2, 6):  # 2-5
                # 计算新金额
                new_amount = prev_yes_amount * n_rebound_percent
                # 更新Yes金额
                yes_entry = self.yes_frame.grid_slaves(row=2*i+1, column=1)[0]
                yes_entry.delete(0, tk.END)
                yes_entry.insert(0, f"{new_amount:.2f}")
                # 更新No金额
                no_entry = self.no_frame.grid_slaves(row=2*i+1, column=1)[0]
                no_entry.delete(0, tk.END)
                no_entry.insert(0, f"{new_amount:.2f}")
                # 更新前一级金额
                prev_yes_amount = new_amount
                prev_no_amount = new_amount
            self.logger.info("金额更新完成")
        except Exception as e:
            self.logger.error(f"设置金额失败: {str(e)}")
            self.update_status("金额设置失败，请检查Cash值是否正确")
            # 如果失败，安排重试
            self.schedule_retry_update()

    def schedule_retry_update(self):
        """安排重试更新金额"""
        self.root.after(5000, self.set_yes_no_cash)  # 5秒后重试

    def start_monitoring(self):
        """开始监控"""
        # 直接使用当前显示的网址
        self.current_url = self.url_entry.get()
        self.logger.info(f"开始监控网址: {self.current_url}")

        # 启用开始按钮，启用停止按钮
        self.start_button['state'] = 'disabled'
        self.stop_button['state'] = 'normal'
        
        # 将"开始监控"文字变为红色
        self.start_button.configure(style='Red.TButton')
        # 恢复"停止监控"文字为黑色
        self.stop_button.configure(style='Black.TButton')

        # 重置交易次数计数器
        self.trade_count = 0
        
        # 启动浏览器作线程
        threading.Thread(target=self._start_browser_monitoring, args=(self.current_url,), daemon=True).start()

        # 启用更金额按钮
        self.update_amount_button['state'] = 'normal'
        # 自动点击更新金额按钮
        self.schedule_update_amount()

        # 启动页面刷新定时器
        self.schedule_refresh()
        # 启动登录状态监控
        self.start_login_monitoring()
        # 启动URL监控
        self.start_url_monitoring()

    def schedule_update_amount(self, retry_count=0):
        """安排更新金额按钮点击，带重试机制"""
        try:
            if retry_count < 15:  # 最多重试15次
                self.logger.info(f"安排更新金额操作 (尝试 {retry_count + 1}/15)")
                # 5秒后执行
                self.root.after(2000, lambda: self.try_update_amount(retry_count))
            else:
                self.logger.warning("更新金额操作达到最大重试次数")
        except Exception as e:
            self.logger.error(f"安排更新金额操作失败: {str(e)}")

    def try_update_amount(self, current_retry=0):
        """尝试更新金额"""
        try:
            self.update_amount_button.invoke()
            self.logger.info("更新金额操作执行成功")
        except Exception as e:
            self.logger.error(f"更新金额操作失败 (尝试 {current_retry + 1}/15): {str(e)}")
            # 如果失败，安排下一次重试
            self.schedule_update_amount(current_retry + 1)
    
    def start_url_monitoring(self):
        """启动URL监控"""
        def check_url():
            if self.running and self.driver:
                try:
                    current_page_url = self.driver.current_url
                    if current_page_url != self.current_url:
                        self.logger.warning(f"检测到URL变化，正在恢复...")
                        self.driver.get(self.current_url)
                        self.logger.info("已恢复到正确的监控网址")
                except Exception as e:
                    self.logger.error(f"URL监控出错: {str(e)}")
                
                # 继续监控
                if self.running:
                    self.url_check_timer = self.root.after(1000, check_url)  # 每秒检查一次
        
        # 开始第一次检查
        self.url_check_timer = self.root.after(1000, check_url)

    def start_login_monitoring(self):
        """启动登录状态监控"""
        def check_login_status():
            if self.running and self.driver:
                try:
                    # 检查登录按钮
                    try:
                        login_button = self.driver.find_element(By.XPATH, 
                            '//*[@id="__pm_viewport"]/nav[1]/div[1]/div[3]/div/nav/div/ul/div[1]/div/button')
                        
                        if login_button.text == "Log In":
                            self.logger.warning("检测到未登录状态，正在执行登录...")
                            self.check_and_handle_login()
                        else:
                            self.logger.debug("当前为登录状态")
                    except NoSuchElementException:
                        # 找不到登录按钮,说明已经登录
                        pass
                    
                except Exception as e:
                    self.logger.error(f"登录状态检查出错: {str(e)}")
                
                # 继续监控
                if self.running:
                    self.login_check_timer = self.root.after(10000, check_login_status)  # 每10秒检查一次
        
        # 开始第一次检查
        self.login_check_timer = self.root.after(20000, check_login_status)

    def _start_browser_monitoring(self, new_url):
        """在新线程中执行浏览器操作"""
        try:
            self.update_status(f"正在尝试访问: {new_url}")
            
            if not self.driver:
                chrome_options = Options()
                chrome_options.debugger_address = "127.0.0.1:9222"
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                
                # Linux特定的Chrome配置
                if platform.system() == 'Linux':
                    chrome_options.add_argument('--disable-gpu')
                    chrome_options.add_argument('--disable-software-rasterizer')
                try:
                    self.driver = webdriver.Chrome(options=chrome_options)
                    self.update_status("连接到浏览器")
                except Exception as e:
                    self.logger.error(f"连接浏览器失败: {str(e)}")
                    self._show_error_and_reset("无法连接Chrome浏览器，请确保已运行start_chrome.sh")
                    return
            try:
                # 在当前标签页打开URL
                self.driver.get(new_url)
                
                # 等待页面加载
                self.update_status("等待页面加载完成...")
                WebDriverWait(self.driver, 60).until(
                    lambda driver: driver.execute_script('return document.readyState') == 'complete'
                )
                
                # 验页面加载成
                current_url = self.driver.current_url
                self.update_status(f"成功加载网: {current_url}")
                
                # 保存配置
                if 'website' not in self.config:
                    self.config['website'] = {}
                self.config['website']['url'] = new_url
                self.save_config()
                
                # 更新交易币对显示
                try:
                    pair = re.search(r'event/([^?]+)', new_url)
                    if pair:
                        self.trading_pair_label.config(text=pair.group(1))
                    else:
                        self.trading_pair_label.config(text="无识别事件名称")
                except Exception:
                    self.trading_pair_label.config(text="解析失败")
                #  开启监控
                self.running = True
                
                # 启动监控线程
                threading.Thread(target=self.monitor_prices, daemon=True).start()
                
            except Exception as e:
                error_msg = f"加载网站失败: {str(e)}"
                self.logger.error(error_msg)
                self._show_error_and_reset(error_msg)  
        except Exception as e:
            error_msg = f"启动监控失败: {str(e)}"
            self.logger.error(error_msg)
            self._show_error_and_reset(error_msg)

    def _show_error_and_reset(self, error_msg):
        """显示错误并置按钮状态"""
        self.update_status(error_msg)
        # 用after方法确保在线程中执行GUI操作
        self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
        self.root.after(0, lambda: self.start_button.config(state='normal'))
        self.root.after(0, lambda: self.stop_button.config(state='disabled'))
        self.running = False

    def stop_monitoring(self):
        """停止监控"""
        try:
            self.running = False
            
            # 停止URL监控
            if self.url_check_timer:
                self.root.after_cancel(self.url_check_timer)
                self.url_check_timer = None
            
            # 停止登录状态监控
            if self.login_check_timer:
                self.root.after_cancel(self.login_check_timer)
                self.login_check_timer = None
            
            self.start_button['state'] = 'normal'
            self.stop_button['state'] = 'disabled'
            self.update_amount_button['state'] = 'disabled'  # 禁用更新金额按钮
            
            # 将"停止监控"文字变为红色
            self.stop_button.configure(style='Red.TButton')
            # 恢复"开始监控"文字为蓝色
            self.start_button.configure(style='Black.TButton')
            if self.driver:
                self.driver.quit()
                self.driver = None
            # 记录最终交易次数
            final_trade_count = self.trade_count
            self.logger.info(f"本次监控共执行 {final_trade_count} 次交易")

            # 取消页面刷新定时器
            if self.refresh_timer:
                self.root.after_cancel(self.refresh_timer)
                self.refresh_timer = None

        except Exception as e:
            self.logger.error(f"停止监控失败: {str(e)}")

    def save_config(self):
        # 从GUI获取并保存配置
        for position, frame in [('Yes', self.yes_frame), ('No', self.no_frame)]:
            entries = [w for w in frame.winfo_children() if isinstance(w, ttk.Entry)]
            
            # 处理目标价格
            target_price = entries[0].get().strip()
            if target_price == '':
                target_price = '0.0'
            self.config['trading'][position]['target_price'] = float(target_price)
            
            # 处理交易数量
            amount = entries[1].get().strip()
            if amount == '':
                amount = '0.0'
            self.config['trading'][position]['amount'] = float(amount)
        
        # 网站地址到历史记录
        current_url = self.url_entry.get().strip()
        if current_url:
            if 'url_history' not in self.config:
                self.config['url_history'] = []
            
            # 如果URL存在，先移除它
            if current_url in self.config['url_history']:
                self.config['url_history'].remove(current_url)
            
            # 将新URL添加到列表开头
            self.config['url_history'].insert(0, current_url)
            
            # 只保留最近6条记录
            self.config['url_history'] = self.config['url_history'][:6]
            
            # 更新下拉列表值
            self.url_entry['values'] = self.config['url_history']
        
        # 保存配置到文件
        with open('config.json', 'w') as f:
            json.dump(self.config, f)

    def update_status(self, message):
        # 检查是否是错误消息
        is_error = any(err in message.lower() for err in ['错误', '失败', 'error', 'failed', 'exception'])
        
        # 更新状态标签，如果是错误则显示红色
        self.status_label.config(
            text=f"状态: {message}",
            foreground='red' if is_error else 'black'
        )
        
        # 错误消息记录到日志文件
        if is_error:
            self.logger.error(message)

    def retry_operation(self, operation, *args, **kwargs):
        """通用重试机制"""
        for attempt in range(self.retry_count):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"{operation.__name__} 失败，尝试 {attempt + 1}/{self.retry_count}: {str(e)}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_interval)
                else:
                    raise

    def monitor_prices(self):
        """检查价格变化"""
        try:
            # 确保浏览器连接
            if not self.driver:
                chrome_options = Options()
                chrome_options.debugger_address = "127.0.0.1:9222"
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                self.driver = webdriver.Chrome(options=chrome_options)
                self.update_status("成功连接到浏览器")
            target_url = self.url_entry.get()
            
            # 使用JavaScript创建并点击链接来打开新标签页
            js_script = """
                const a = document.createElement('a');
                a.href = arguments[0];
                a.target = '_blank';
                a.rel = 'noopener noreferrer';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            """
            self.driver.execute_script(js_script, target_url)
            
            # 等待新标签页打开
            time.sleep(1)
            
            # 切换到新打开的标签页
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            # 等待页面加载完成
            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            self.update_status(f"已在新标签页打开: {target_url}")   
                
            # 开始监控价格
            while self.running:
                try:
                    self.check_prices()
                    self.check_balance()
                    time.sleep(1)
                except Exception as e:
                    self.logger.error(f"监控失败: {str(e)}")
                    time.sleep(self.retry_interval) 
        except Exception as e:
            self.logger.error(f"加载页面失败: {str(e)}")
            self.update_status(f"加载页面失败: {str(e)}")
            self.stop_monitoring()
        except Exception as e:
            self.logger.error(f"监控过程出错: {str(e)}")
            self.update_status("监控出错，请查看日志")
            self.stop_monitoring()

    def check_prices(self):
        """检查价格变化"""
        try:
            if not self.driver:
                raise Exception("浏览器连接丢失")
            
            # 等待页面完全加载
            WebDriverWait(self.driver, 20).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            try:
                # 使用JavaScript直接获取价格
                prices = self.driver.execute_script("""
                    function getPrices() {
                        const prices = {yes: null, no: null};
                        const elements = document.getElementsByTagName('span');
                        
                        for (let el of elements) {
                            const text = el.textContent.trim();
                            if (text.includes('Yes') && text.includes('¢')) {
                                const match = text.match(/(\\d+\\.?\\d*)¢/);
                                if (match) prices.yes = parseFloat(match[1]);
                            }
                            if (text.includes('No') && text.includes('¢')) {
                                const match = text.match(/(\\d+\\.?\\d*)¢/);
                                if (match) prices.no = parseFloat(match[1]);
                            }
                        }
                        return prices;
                    }
                    return getPrices();
                """)
                
                if prices['yes'] is not None and prices['no'] is not None:
                    yes_price = float(prices['yes']) / 100
                    no_price = float(prices['no']) / 100
                    
                    # 更新价格显示
                    self.yes_price_label.config(
                        text=f"Yes: {prices['yes']}¢ (${yes_price:.2f})",
                        foreground='red'
                    )
                    self.no_price_label.config(
                        text=f"No: {prices['no']}¢ (${no_price:.2f})",
                        foreground='red'
                    )
                    
                    # 更新最后更新时间
                    current_time = datetime.now().strftime('%H:%M:%S')
                    self.last_update_label.config(text=f"最后更新: {current_time}")
                    
                    # 执行所有交易检查函数
                    self.First_trade()
                    self.Second_trade()
                    self.Third_trade()
                    self.Forth_trade()
                    self.Fifth_trade()
                    self.Sixth_trade()
                    self.Sell_yes()  # 添加自动卖出检查
                    self.Sell_no()   # 添加自动卖出检查
                    
                else:
                    self.update_status("无法获取价格数据")  
            except Exception as e:
                self.logger.error(f"价格获取失败: {str(e)}")
                self.update_status(f"价格获取失败: {str(e)}")
                self.yes_price_label.config(text="Yes: 获取失败", foreground='red')
                self.no_price_label.config(text="No: 获取失败", foreground='red') 
        except Exception as e:
            self.logger.error(f"检查价格失败: {str(e)}")
            self.update_status(f"价检查错误: {str(e)}")
            time.sleep(2)

    def _handle_metamask_popup(self):
        """处理 MetaMask 扩展弹窗的键盘操作"""
        try:
            # 直接等待一段时间让MetaMask扩展弹窗出现
            time.sleep(1)
            # 模拟键盘操作序列
            # 1. 按6次TAB
            for _ in range(6):
                pyautogui.press('tab')
                time.sleep(0.1)  # 每次按键之间添加短暂延迟
            # 2. 按1次ENTER
            pyautogui.press('enter')
            time.sleep(0.1)  # 等待第一次确认响应
            # 3. 按2次TAB
            for _ in range(2):
                pyautogui.press('tab')
                time.sleep(0.1)
            # 4. 按1次ENTER
            pyautogui.press('enter')
            # 等待弹窗自动关闭
            time.sleep(0.3)
            self.logger.info("MetaMask 扩展弹窗操作完成")
        except Exception as e:
            error_msg = f"处理 MetaMask 扩展弹窗失败: {str(e)}"
            self.logger.error(error_msg)
            self.update_status(error_msg)
            raise

    def monitor_sell_conditions(self, position, buy_time, buy_price):
        """监控卖出条件"""
        while self.running:
            current_time = time.time()
            time_elapsed = current_time - buy_time
            try:
                # 获当价格
                price_element = self.driver.find_element(By.XPATH, f"//button[contains(@class, '{position.lower()}')]")
                price_text = price_element.text
                current_price = float(price_text.split()[1].replace('¢', '')) / 100
                
                profit_percentage = (current_price - buy_price) / buy_price * 100
                
                self.update_status(f"{position} 持仓状态 - 买入价: ${buy_price:.2f}, 当前价: {price_text}, 盈利: {profit_percentage:.2f}%")
                
                # 检查是否满足卖出条件
                if (profit_percentage >= self.config['sell_condition']['profit_percentage'] or 
                    time_elapsed >= self.config['sell_condition']['time_limit']):
                    self.execute_sell(position)
                    break
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"监控卖出条件出错: {str(e)}")
                continue

    def execute_sell(self, position):
        """执行卖出操作"""
        try:
            # 点击卖出按钮
            sell_button = self.driver.find_element(By.XPATH, f"//div[contains(text(), '{position}')]/..//button[contains(text(), '卖出')]")
            sell_button.click()
            
            # 确认卖出
            confirm_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), '确认卖出')]"))  # 添加缺失的右括号
            )  # 添加缺失的右括号
            confirm_button.click()    
        except Exception as e:  # 添加异常处理
            self.logger.error(f"执行卖出操作出错: {str(e)}")
            self.update_status(f"卖出操作失败: {str(e)}")
            raise  # 重新抛出异常以便上层处理

    def run(self):
        try:
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"GUI运行错误: {str(e)}")
            sys.exit(1)

    def click_website_button(self, button_type):
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return   
            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            # 根据按钮类型查找并点击对应的网站按钮
            if button_type == "Buy":
                xpath = "//button[contains(@class, 'Buy') or .//span[contains(text(), 'Buy')]]"
            elif button_type == "Sell":
                xpath = "//button[contains(@class, 'Sell') or .//span[contains(text(), 'Sell')]]"
            elif button_type == "Max":
                xpath = "//button[contains(text(), 'Max') or .//span[contains(text(), 'Max')]]"
            elif button_type == "Buy-Confirm":
                # 使用固定的XPath路径
                xpath = '//div[@class="c-dhzjXW c-dhzjXW-ihxUIch-css"]//button'
            elif button_type == "SetExpBuy":
                # 先点击 Set Expiration
                exp_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Set Expiration')]"))
                )
                exp_button.click()
                time.sleep(1)  # 等待弹窗出现
                
                xpath = "//div[contains(@class, 'modal')]//button[contains(text(), 'Buy')]"
            else:
                self.update_status(f"未知的按钮类型: {button_type}")
                return
            # 查找并点击按钮
            button = WebDriverWait(self.driver, 10).until(  
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            
            # 执行点击
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status(f"已点击网站上的 {button_type} 按钮")  
        except TimeoutException:
            self.logger.error(f"点击按钮超时: {button_type}")
            self.update_status(f"点击按钮超时: {button_type}")
        except Exception as e:
            self.logger.error(f"点击网站按钮失败: {str(e)}")
            self.update_status(f"点击网站按钮失败: {str(e)}")

    def click_position_sell_no(self):
        """点击 Positions-Sell-No 按钮"""
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            position_value = None
            try:
                # 尝试获取第一行YES的标签值，如果不存在会直接进入except块
                first_position = WebDriverWait(self.driver, 2).until(  # 缩短等待时间到2秒
                    EC.presence_of_element_located((By.XPATH, 
                        '//div[@class="c-dhzjXW c-chKWaB c-chKWaB-eVTycx-color-green c-dhzjXW-ibxvuTL-css" and text()="Yes"]'))
                )# //div[@class="c-dhzjXW c-chKWaB c-chKWaB-eVTycx-color-green c-dhzjXW-ibxvuTL-css" and text()="Yes"]
                position_value = first_position.text
            except:
                # 如果获取第一行失败，不报错，继续执行
                pass   
            # 根据position_value的值决定点击哪个按钮
            if position_value == "Yes":
                # 如果第一行是Yes，点击第二的按钮
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, 
                        '(//button[@class="c-gBrBnR c-gBrBnR-iifsICY-css"])[2]'))
                )
            else:
                # 如果第一行不存在或不是Yes，使用默认的第一行按钮
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, 
                        '(//button[@class="c-gBrBnR c-gBrBnR-iifsICY-css"])'))
                )
            # 执行点击
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Positions-Sell-No 按钮")  
        except Exception as e:
            error_msg = f"点击 Positions-Sell-No 按钮失败: {str(e)}"
            self.logger.error(error_msg)
            self.update_status(error_msg)

    def click_position_sell(self):
        """点击 Positions-Sell-Yes 按钮，函数名漏写了一个 YES"""
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            position_value = None
            try:
                # 尝试获取第二行NO的标签值，如果不存在会直接进入except块
                second_position = WebDriverWait(self.driver, 2).until(  # 缩短等待时间到2秒
                    EC.presence_of_element_located((By.XPATH, 
                        '//*[@id="event-layout-with-side-nav"]/div[1]/div/div/div[2]/div/div[2]/div/div[2]/table/tbody/tr[1]/td[6]/div/button'))
                )
            except:
                # 如果获取第二行失败，不报错，继续执行
                pass
                
            # 根据position_value的值决定点击哪个按钮
            if position_value == "No":
                # 如果第二行是No，点击第一行YES 的 SELL的按钮
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, 
                        '(//button[@class="c-gBrBnR c-gBrBnR-iifsICY-css"])[1]'))
                )
            else:
                # 如果第二行不存在或不是No，使用默认的第一行按钮
                button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, 
                        '(//button[@class="c-gBrBnR c-gBrBnR-iifsICY-css"])'))
                )
            # 执行点击
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Positions-Sell-Yes 按钮")  
        except Exception as e:
            error_msg = f"点击 Positions-Sell-Yes 按钮失败: {str(e)}"
            self.logger.error(error_msg)
            self.update_status(error_msg)

    def click_profit_sell(self):
        """点击卖出盈利按钮并处理 MetaMask 弹窗"""
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            # 点击Sell-卖出按钮
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    '//div[@class="c-dhzjXW c-dhzjXW-ihxUIch-css"]//button'))
            )
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击卖出盈利按钮")
            # 等待MetaMask弹窗出现
            time.sleep(1)
            # 使用统一的MetaMask弹窗处理方法
            self._handle_metamask_popup()
            """ 等待 5 秒，刷新 2 次，预防交易失败 """
            # 等待交易完成
            time.sleep(4)
            self.driver.refresh()
            self.update_status("交易完成并刷新页面")
        except Exception as e:
            error_msg = f"卖出盈利操作失败: {str(e)}"
            self.logger.error(error_msg)
            self.update_status(error_msg)

    def check_balance(self):
        """获取Portfolio和Cash值"""
        try:
            if not self.driver:
                raise Exception("浏览器连接丢失")
            # 等待页面完全加载
            WebDriverWait(self.driver, 20).until(
                lambda driver: driver.execute_script('return document.readyState') == 'complete'
            )
            
            try:
                # 取Portfolio值
                portfolio_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, 
                        '(//span[@class="c-PJLV c-jaFKlk c-PJLV-ibdakYG-css"])[1]'))
                )
                portfolio_value = portfolio_element.text
                
                # 获取Cash值
                cash_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, 
                        '(//span[@class="c-PJLV c-jaFKlk c-PJLV-ibdakYG-css"])[2]'))
                )
                cash_value = cash_element.text
                
                # 更新Portfolio和Cash显示
                self.portfolio_label.config(text=f"Portfolio: {portfolio_value}")
                self.cash_label.config(text=f"Cash: {cash_value}")
                
                # 新最后更新间
                current_time = datetime.now().strftime('%H:%M:%S')
                self.balance_update_label.config(text=f"最后更新: {current_time}")  
            except Exception as e:
                self.logger.error(f"获取金信息失败: {str(e)}")
                self.portfolio_label.config(text="Portfolio: 获取失败")
                self.cash_label.config(text="Cash: 获取失败")
        except Exception as e:
            self.logger.error(f"检查资金失败: {str(e)}")
            self.update_status(f"资金检查错误: {str(e)}")
            time.sleep(2)

    def click_buy(self):
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="event-layout-with-side-nav"]/div[2]/div/div[1]/div/div[1]/div/div/div[1]'))
            )
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Buy 按钮")
        except Exception as e:
            self.logger.error(f"点击 Buy 按钮失败: {str(e)}")
            self.update_status(f"点击 Buy 按钮失败: {str(e)}")

    def click_sell(self):
        """点击 Sell 按钮"""
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="event-layout-with-side-nav"]/div[2]/div/div[1]/div/div[1]/div/div/div[2]'))
            )
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Sell 按钮")
        except Exception as e:
            self.logger.error(f"点击 Sell 按钮失败: {str(e)}")
            self.update_status(f"点击 Sell 按钮失败: {str(e)}")

    def click_buy_yes(self):
        """点击 Buy-Yes 按钮"""
        try:
            if not self.driver:
                self.update_status("请先连接浏器")
                return
            
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="event-layout-with-side-nav"]/div[2]/div/div[1]/div/div[2]/div[1]/div[2]/div/div[1]/div'))
            )
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Buy-Yes 按钮")
        except Exception as e:
            self.logger.error(f"点击 Buy-Yes 按钮失败: {str(e)}")
            self.update_status(f"点击 Buy-Yes 按钮失败: {str(e)}")

    def click_buy_no(self):
        """点击 Buy-No 按钮"""
        try:
            if not self.driver:
                self.update_status("请先连接浏器")
                return
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    '//*[@id="event-layout-with-side-nav"]/div[2]/div/div[1]/div/div[2]/div[1]/div[2]/div/div[2]/div'))
            )# //div[@class="c-dhzjXW c-dhzjXW-ibzvESn-css"]
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Buy-No 按钮")
        except Exception as e:
            self.logger.error(f"点击 Buy-No 按钮失败: {str(e)}")
            self.update_status(f"点击 Buy-No 按钮失败: {str(e)}")

    def click_sell_yes(self):
        """点击 Sell-Yes 按钮"""
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    '//*[@id="event-layout-with-side-nav"]/div[2]/div/div[1]/div/div[2]/div[1]/div[2]/div[1]/div[1]/div'))
            )# //div[@class="c-dhzjXW c-dhzjXW-iiUtrmZ-css"]
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Sell-Yes 按钮")
        except Exception as e:
            self.logger.error(f"点击 Sell-Yes 按钮失败: {str(e)}")
            self.update_status(f"点击 Sell-Yes 按钮失败: {str(e)}")

    def click_sell_no(self):
        """点击 Sell-No 按钮"""
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    '//*[@id="event-layout-with-side-nav"]/div[2]/div/div[1]/div/div[2]/div[1]/div[2]/div[1]/div[2]/div'))
            )# //div[@class="c-dhzjXW c-dhzjXW-ibzvESn-css"]
            self.driver.execute_script("arguments[0].click();", button)
            self.update_status("已点击 Sell-No 按钮")
        except Exception as e:
            self.logger.error(f"点击 Sell-No 按钮失败: {str(e)}")
            self.update_status(f"点击 Sell-No 按钮失败: {str(e)}")

    def click_amount(self, event=None):
        """点击 Amount 按钮并输入数量"""
        try:
            if not self.driver:
                self.update_status("请先连接浏览器")
                return
            # 获取触发事件的按钮
            button = event.widget if event else self.amount_button
            button_text = button.cget("text")
            # 找到输入框
            amount_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="event-layout-with-side-nav"]/div[2]/div/div[1]/div/div[2]/div[2]/div[2]/input'))
            )# //input[@class="c-ecshmo c-ecshmo-ielLCmU-css"]
            # 清空输入框
            amount_input.clear()
            # 根据按钮文本获取对应的金额
            if button_text == "Amount-Yes0":
                amount = self.yes_amount_entry.get()
            elif button_text == "Amount-Yes1":
                yes1_amount_entry = self.yes_frame.grid_slaves(row=3, column=1)[0]
                amount = yes1_amount_entry.get()
            elif button_text == "Amount-Yes2":
                yes2_amount_entry = self.yes_frame.grid_slaves(row=5, column=1)[0]
                amount = yes2_amount_entry.get()
            elif button_text == "Amount-Yes3":
                yes3_amount_entry = self.yes_frame.grid_slaves(row=7, column=1)[0]
                amount = yes3_amount_entry.get()
            elif button_text == "Amount-Yes4":
                yes4_amount_entry = self.yes_frame.grid_slaves(row=9, column=1)[0]
                amount = yes4_amount_entry.get()
            elif button_text == "Amount-Yes5":
                yes5_amount_entry = self.yes_frame.grid_slaves(row=11, column=1)[0]
                amount = yes5_amount_entry.get()
            elif button_text == "Amount-No0":
                amount = self.no_amount_entry.get()
            elif button_text == "Amount-No1":
                no1_amount_entry = self.no_frame.grid_slaves(row=3, column=1)[0]
                amount = no1_amount_entry.get()
            elif button_text == "Amount-No2":
                no2_amount_entry = self.no_frame.grid_slaves(row=5, column=1)[0]
                amount = no2_amount_entry.get()
            elif button_text == "Amount-No3":
                no3_amount_entry = self.no_frame.grid_slaves(row=7, column=1)[0]
                amount = no3_amount_entry.get()
            elif button_text == "Amount-No4":
                no4_amount_entry = self.no_frame.grid_slaves(row=9, column=1)[0]
                amount = no4_amount_entry.get()
            elif button_text == "Amount-No5":
                no5_amount_entry = self.no_frame.grid_slaves(row=11, column=1)[0]
                amount = no5_amount_entry.get()
            else:
                amount = "0.0"
            # 输入金额
            amount_input.send_keys(str(amount))
            
            self.update_status(f"已在Amount输入框输入: {amount}")    
        except Exception as e:
            self.logger.error(f"Amount操作失败: {str(e)}")
            self.update_status(f"Amount操作失败: {str(e)}")

    def First_trade(self):
        """处理Yes0/No0的自动交易"""
        try:
            self.is_trading = True  # 设置交易状态
            if not self.driver:
                raise Exception("浏览器连接丢失")   
            # 获取当前Yes和No价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Yes') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.yes = parseFloat(match[1]);
                        }
                        if (text.includes('No') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.no = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['yes'] is not None and prices['no'] is not None:
                yes_price = float(prices['yes']) / 100
                no_price = float(prices['no']) / 100
                
                # 获取Yes0和No0的目标价格
                yes0_target = float(self.yes_price_entry.get())
                no0_target = float(self.no_price_entry.get())
                
                # 检查Yes0价格匹配
                if abs(yes0_target - yes_price) < 0.0001 and yes0_target > 0:
                    self.logger.info("Yes 0价格匹配，执行自动交易")
                    # 执行现有的交易操作
                    self.amount_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(0.5)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("First_trade")
                    
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy Yes 0",
                        price=yes_price,
                        amount=float(self.yes_amount_entry.get()),
                        trade_count=self.trade_count
                    )

                    # 重置Yes0和No0价格为0.00
                    self.yes_price_entry.delete(0, tk.END)
                    self.yes_price_entry.insert(0, "0.00")
                    self.no_price_entry.delete(0, tk.END)
                    self.no_price_entry.insert(0, "0.00")
                    
                    # 设置No1价格为0.53
                    no1_price_entry = self.no_frame.grid_slaves(row=2, column=1)[0]
                    no1_price_entry.delete(0, tk.END)
                    no1_price_entry.insert(0, "0.53")
                    # 设置 Yes6和No6价格为0.85
                    yes6_price_entry = self.yes_frame.grid_slaves(row=12, column=1)[0]
                    yes6_price_entry.delete(0, tk.END)
                    yes6_price_entry.insert(0, "0.99")
                    no6_price_entry = self.no_frame.grid_slaves(row=12, column=1)[0]
                    no6_price_entry.delete(0, tk.END)
                    no6_price_entry.insert(0, "0.99")
                    # 增加等待 1秒
                    time.sleep(1)
                    
                # 检查No0价格匹配
                elif abs(no0_target - no_price) < 0.0001 and no0_target > 0:
                    self.logger.info("No 0价格匹配，执行自动交易") 
                    # 执行现有的交易操作
                    self.buy_no_button.invoke()
                    time.sleep(0.5)
                    self.amount_no0_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("First_trade")
                    
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy No 0",
                        price=no_price,
                        amount=float(self.no_amount_entry.get()),
                        trade_count=self.trade_count
                    )
                    
                    # 重置Yes0和No0价格为0.00
                    self.yes_price_entry.delete(0, tk.END)
                    self.yes_price_entry.insert(0, "0.00")
                    self.no_price_entry.delete(0, tk.END)
                    self.no_price_entry.insert(0, "0.00")
                    
                    # 设置Yes1价格为0.53
                    yes1_price_entry = self.yes_frame.grid_slaves(row=2, column=1)[0]
                    yes1_price_entry.delete(0, tk.END)
                    yes1_price_entry.insert(0, "0.53")
                    # 设置 Yes6和No6价格为0.85
                    yes6_price_entry = self.yes_frame.grid_slaves(row=12, column=1)[0]
                    yes6_price_entry.delete(0, tk.END)
                    yes6_price_entry.insert(0, "0.99")
                    no6_price_entry = self.no_frame.grid_slaves(row=12, column=1)[0]
                    no6_price_entry.delete(0, tk.END)
                    no6_price_entry.insert(0, "0.99")
                    # 增加等待 1秒
                    time.sleep(1)
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"First_trade执行失败: {str(e)}")
            self.update_status(f"First_trade执行失败: {str(e)}")
        finally:
            self.is_trading = False  # 重置交易状态

    def Second_trade(self):
        """处理Yes1/No1的自动交易"""
        try:
            self.is_trading = True
            if not self.driver:
                raise Exception("浏览器连接丢失")
                
            # 获取当前Yes和No价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Yes') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.yes = parseFloat(match[1]);
                        }
                        if (text.includes('No') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.no = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['yes'] is not None and prices['no'] is not None:
                yes_price = float(prices['yes']) / 100
                no_price = float(prices['no']) / 100
                
                # 获Yes1和No1的价格输入框
                yes1_price_entry = self.yes_frame.grid_slaves(row=2, column=1)[0]
                no1_price_entry = self.no_frame.grid_slaves(row=2, column=1)[0]
                yes1_target = float(yes1_price_entry.get())
                no1_target = float(no1_price_entry.get())
                
                # 检查Yes1价格匹配
                if abs(yes1_target - yes_price) < 0.0001 and yes1_target > 0:
                    self.logger.info("Yes 1价格匹配，执行自动交易")
                    # 执行现有的交易操作
                    self.amount_yes1_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Second_trade")

                    # 重置Yes1和No1价格为0.00
                    yes1_price_entry.delete(0, tk.END)
                    yes1_price_entry.insert(0, "0.00")
                    no1_price_entry.delete(0, tk.END)
                    no1_price_entry.insert(0, "0.00")
                    
                    # 设置No2价格为0.53
                    no2_price_entry = self.no_frame.grid_slaves(row=4, column=1)[0]
                    no2_price_entry.delete(0, tk.END)
                    no2_price_entry.insert(0, "0.53")
                    
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy Yes 1",
                        price=yes_price,
                        amount=float(self.yes1_amount_entry.get()),
                        trade_count=self.trade_count
                    )
                    
                # 检查No1价格匹配
                elif abs(no1_target - no_price) < 0.0001 and no1_target > 0:
                    self.logger.info("No 1价格匹配，执行自动交易")
                    
                    # 执行现有的交易操作
                    self.buy_no_button.invoke()
                    time.sleep(0.5)
                    self.amount_no1_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Second_trade")

                    # 重置Yes1和No1价格为0.00
                    yes1_price_entry.delete(0, tk.END)
                    yes1_price_entry.insert(0, "0.00")
                    no1_price_entry.delete(0, tk.END)
                    no1_price_entry.insert(0, "0.00")
                    
                    # 设置Yes2价格为0.53
                    yes2_price_entry = self.yes_frame.grid_slaves(row=4, column=1)[0]
                    yes2_price_entry.delete(0, tk.END)
                    yes2_price_entry.insert(0, "0.53")
                    
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy No 1",
                        price=no_price,
                        amount=float(no1_price_entry.get()),
                        trade_count=self.trade_count
                    )
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Second_trade执行失败: {str(e)}")
            self.update_status(f"Second_trade执行失败: {str(e)}")
        finally:
            self.is_trading = False

    def Third_trade(self):
        """处理Yes2/No2的自动交易"""
        try:
            self.is_trading = True
            if not self.driver:
                raise Exception("浏览器连接丢失")  
            # 获取当前Yes和No价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Yes') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.yes = parseFloat(match[1]);
                        }
                        if (text.includes('No') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.no = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['yes'] is not None and prices['no'] is not None:
                yes_price = float(prices['yes']) / 100
                no_price = float(prices['no']) / 100
                
                # 获取Yes2和No2的价格输入框
                yes2_price_entry = self.yes_frame.grid_slaves(row=4, column=1)[0]
                no2_price_entry = self.no_frame.grid_slaves(row=4, column=1)[0]
                yes2_target = float(yes2_price_entry.get())
                no2_target = float(no2_price_entry.get())
                
                # 检查Yes2价格匹配
                if abs(yes2_target - yes_price) < 0.0001 and yes2_target > 0:
                    self.logger.info("Yes 2价格匹配，执行自动交易")
                    # 执行交易操作
                    self.amount_yes2_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Third_trade")
                    
                    # 重置Yes2和No2价格为0.00
                    yes2_price_entry.delete(0, tk.END)
                    yes2_price_entry.insert(0, "0.00")
                    no2_price_entry.delete(0, tk.END)
                    no2_price_entry.insert(0, "0.00")
                    
                    # 设置No3价格为0.53
                    no3_price_entry = self.no_frame.grid_slaves(row=6, column=1)[0]
                    no3_price_entry.delete(0, tk.END)
                    no3_price_entry.insert(0, "0.53")
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy Yes 2",
                        price=yes_price,
                        amount=float(yes2_price_entry.get()),
                        trade_count=self.trade_count
                    )   
                # 检查No2价格匹配
                elif abs(no2_target - no_price) < 0.0001 and no2_target > 0:
                    self.logger.info("No 2价格匹配，执行自动交易")
                    # 执行交易操作
                    self.buy_no_button.invoke()
                    time.sleep(0.5)
                    self.amount_no2_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Third_trade")
                    
                    # 重置Yes2和No2价格为0.00
                    yes2_price_entry.delete(0, tk.END)
                    yes2_price_entry.insert(0, "0.00")
                    no2_price_entry.delete(0, tk.END)
                    no2_price_entry.insert(0, "0.00")
                    
                    # 设置Yes3价格为0.53
                    yes3_price_entry = self.yes_frame.grid_slaves(row=6, column=1)[0]
                    yes3_price_entry.delete(0, tk.END)
                    yes3_price_entry.insert(0, "0.53")
                   
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy No 2",
                        price=no_price,
                        amount=float(no2_price_entry.get()),
                        trade_count=self.trade_count
                    )
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Third_trade执行失败: {str(e)}")
            self.update_status(f"Third_trade执行失败: {str(e)}")
        finally:
            self.is_trading = False

    def Forth_trade(self):
        """处理Yes3/No3的自动交易"""
        try:
            self.is_trading = True
            if not self.driver:
                raise Exception("浏览器连接丢失")
                
            # 获取当前Yes和No价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Yes') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.yes = parseFloat(match[1]);
                        }
                        if (text.includes('No') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.no = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['yes'] is not None and prices['no'] is not None:
                yes_price = float(prices['yes']) / 100
                no_price = float(prices['no']) / 100
                
                # 获取Yes3和No3的价格输入框
                yes3_price_entry = self.yes_frame.grid_slaves(row=6, column=1)[0]
                no3_price_entry = self.no_frame.grid_slaves(row=6, column=1)[0]
                yes3_target = float(yes3_price_entry.get())
                no3_target = float(no3_price_entry.get())
                
                # 检查Yes3价格匹配
                if abs(yes3_target - yes_price) < 0.0001 and yes3_target > 0:
                    self.logger.info("Yes 3价格匹配，执行自动交易")
                    # 执行交易操作
                    self.amount_yes3_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Forth_trade")
                    
                    # 重置Yes3和No3价格为0.00
                    yes3_price_entry.delete(0, tk.END)
                    yes3_price_entry.insert(0, "0.00")
                    no3_price_entry.delete(0, tk.END)
                    no3_price_entry.insert(0, "0.00")
                    
                    # 设置No4价格为0.53
                    no4_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                    no4_price_entry.delete(0, tk.END)
                    no4_price_entry.insert(0, "0.53")
                # 检查No3价格匹配
                elif abs(no3_target - no_price) < 0.0001 and no3_target > 0:
                    self.logger.info("No 3价格匹配，执行自动交易")
                    # 执行交易操作
                    self.buy_no_button.invoke()
                    time.sleep(0.5)
                    self.amount_no3_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Forth_trade")
                    
                    # 重置Yes3和No3价格为0.00
                    yes3_price_entry.delete(0, tk.END)
                    yes3_price_entry.insert(0, "0.00")
                    no3_price_entry.delete(0, tk.END)
                    no3_price_entry.insert(0, "0.00")
                    
                    # 设置Yes4价格为0.53
                    yes4_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                    yes4_price_entry.delete(0, tk.END)
                    yes4_price_entry.insert(0, "0.53")

                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy No 3",
                        price=no_price,
                        amount=float(no3_price_entry.get()),
                        trade_count=self.trade_count
                    )
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Forth_trade执行失败: {str(e)}")
            self.update_status(f"Forth_trade执行失败: {str(e)}")
        finally:
            self.is_trading = False

    def Fifth_trade(self):
        """处理Yes4/No4的自动交易"""
        try:
            self.is_trading = True
            if not self.driver:
                raise Exception("浏览器连接丢失")
                
            # 获取当前Yes和No价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Yes') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.yes = parseFloat(match[1]);
                        }
                        if (text.includes('No') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.no = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['yes'] is not None and prices['no'] is not None:
                yes_price = float(prices['yes']) / 100
                no_price = float(prices['no']) / 100
                
                # 获取Yes4和No4的价格输入框
                yes4_price_entry = self.yes_frame.grid_slaves(row=8, column=1)[0]
                no4_price_entry = self.no_frame.grid_slaves(row=8, column=1)[0]
                yes4_target = float(yes4_price_entry.get())
                no4_target = float(no4_price_entry.get())
                
                # 检查Yes4价格匹配
                if abs(yes4_target - yes_price) < 0.0001 and yes4_target > 0:
                    self.logger.info("Yes 4价格匹配，执行自动交易")
                    # 执行交易操作
                    self.amount_yes4_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Fifth_trade")
                    
                    # 重置Yes4和No4价格为0.00
                    yes4_price_entry.delete(0, tk.END)
                    yes4_price_entry.insert(0, "0.00")
                    no4_price_entry.delete(0, tk.END)
                    no4_price_entry.insert(0, "0.00")
                    
                    # 设No5价格为0.53
                    no5_price_entry = self.no_frame.grid_slaves(row=10, column=1)[0]
                    no5_price_entry.delete(0, tk.END)
                    no5_price_entry.insert(0, "0.53")

                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy Yes 4",
                        price=yes_price,
                        amount=float(yes4_price_entry.get()),
                        trade_count=self.trade_count
                    )
                # 检查No4价格匹配
                elif abs(no4_target - no_price) < 0.0001 and no4_target > 0:
                    self.logger.info("No 4价格匹配，执行自动交易")  
                    # 执行交易操作
                    self.buy_no_button.invoke()
                    time.sleep(0.5)
                    self.amount_no4_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Fifth_trade")
                    
                    # 重置Yes4和No4价格为0.00
                    yes4_price_entry.delete(0, tk.END)
                    yes4_price_entry.insert(0, "0.00")
                    no4_price_entry.delete(0, tk.END)
                    no4_price_entry.insert(0, "0.00")
                    
                    # 设置Yes5价格为0.53
                    yes5_price_entry = self.yes_frame.grid_slaves(row=10, column=1)[0]
                    yes5_price_entry.delete(0, tk.END)
                    yes5_price_entry.insert(0, "0.53")

                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy No 4",
                        price=no_price,
                        amount=float(no4_price_entry.get()),
                        trade_count=self.trade_count
                    )
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Fifth_trade执行失败: {str(e)}")
            self.update_status(f"Fifth_trade执行失败: {str(e)}")
        finally:
            self.is_trading = False

    def Sixth_trade(self):
        """处理Yes5/No5的自动交易"""
        try:
            self.is_trading = True
            if not self.driver:
                raise Exception("浏览器连接丢失")
                
            # 获取当前Yes和No价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Yes') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.yes = parseFloat(match[1]);
                        }
                        if (text.includes('No') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.no = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['yes'] is not None and prices['no'] is not None:
                yes_price = float(prices['yes']) / 100
                no_price = float(prices['no']) / 100
                
                # 获取Yes5和No5的价格输入框
                yes5_price_entry = self.yes_frame.grid_slaves(row=10, column=1)[0]
                no5_price_entry = self.no_frame.grid_slaves(row=10, column=1)[0]
                yes5_target = float(yes5_price_entry.get())
                no5_target = float(no5_price_entry.get())
                
                # 检查Yes5价格匹配
                if abs(yes5_target - yes_price) < 0.0001 and yes5_target > 0:
                    self.logger.info("Yes 5价格匹配，执行自动交易")
                    # 执行交易操作
                    self.amount_yes5_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Sixth_trade")
                    
                    # 重置Yes5和No5价格为0.00
                    yes5_price_entry.delete(0, tk.END)
                    yes5_price_entry.insert(0, "0.00")
                    no5_price_entry.delete(0, tk.END)
                    no5_price_entry.insert(0, "0.00")

                    """当买了 6次后预防第 7 次反水，所以价格到了 50 时就平仓，然后再自动开"""
                    # 设置 Yes6和No6价格为0.98
                    yes6_price_entry = self.yes_frame.grid_slaves(row=12, column=1)[0]
                    yes6_price_entry.delete(0, tk.END)
                    yes6_price_entry.insert(0, "0.99")
                    no6_price_entry = self.no_frame.grid_slaves(row=12, column=1)[0]
                    no6_price_entry.delete(0, tk.END)
                    no6_price_entry.insert(0, "0.5")
                    
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy Yes 5",
                        price=yes_price,
                        amount=float(yes5_price_entry.get()),
                        trade_count=self.trade_count
                    )
                # 检查No5价格匹配
                elif abs(no5_target - no_price) < 0.0001 and no5_target > 0:
                    self.logger.info("No 5价格匹配，执行自动交易")
                    
                    # 执行交易操作
                    self.buy_no_button.invoke()
                    time.sleep(0.5)
                    self.amount_no5_button.event_generate('<Button-1>')
                    time.sleep(0.5)
                    self.buy_confirm_button.invoke()
                    time.sleep(1)
                    self._handle_metamask_popup()
                    # 执行等待和刷新
                    self.sleep_refresh("Sixth_trade")
                    
                    # 重置Yes5和No5价格为0.00
                    yes5_price_entry.delete(0, tk.END)
                    yes5_price_entry.insert(0, "0.00")
                    no5_price_entry.delete(0, tk.END)
                    no5_price_entry.insert(0, "0.00")

                    """当买了 4 次后预防第 5 次反水，所以价格到了 50 时就平仓，然后再自动开"""
                    # 设置 Yes6和No6价格为0.85
                    yes6_price_entry = self.yes_frame.grid_slaves(row=12, column=1)[0]
                    yes6_price_entry.delete(0, tk.END)
                    yes6_price_entry.insert(0, "0.5")
                    no6_price_entry = self.no_frame.grid_slaves(row=12, column=1)[0]
                    no6_price_entry.delete(0, tk.END)
                    no6_price_entry.insert(0, "0.99")
                    # 增加交易次数
                    self.trade_count += 1
                    # 发送交易邮件
                    self.send_trade_email(
                        trade_type="Buy No 5",
                        price=no_price,
                        amount=float(no5_price_entry.get()),
                        trade_count=self.trade_count
                    )
        except ValueError as e:
            self.logger.error(f"价格转换错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"Sixth_trade执行失败: {str(e)}")
            self.update_status(f"Sixth_trade执行失败: {str(e)}")
        finally:
            self.is_trading = False

    def Sell_yes(self):
        """当YES6价格等于实时Yes价格时自动卖出"""
        try:
            self.is_trading = True
            if not self.driver:
                raise Exception("浏览器连接丢失")
                
            # 获取当前Yes价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('Yes') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.yes = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['yes'] is not None:
                yes_price = float(prices['yes']) / 100
                # 获取Yes6价格
                yes6_price_entry = self.yes_frame.grid_slaves(row=12, column=1)[0]
                no6_price_entry = self.no_frame.grid_slaves(row=12, column=1)[0]
                yes6_target = float(yes6_price_entry.get())
                # 检查Yes6价格匹配
                if abs(yes6_target - yes_price) < 0.0001 and yes6_target > 0:
                    self.logger.info("Yes6价格匹配，执行自动卖出")
                    # 点击Positions-Sell-Yes按钮
                    self.position_sell_yes_button.invoke()
                    time.sleep(0.5)
                    # 点击Sell-卖出按钮
                    self.sell_profit_button.invoke()
                    # 等待3秒
                    time.sleep(3)
                    # 执行等待和刷新
                    self.sleep_refresh("Sell_yes")
                    
                    # 发送交易邮件 - 卖出YES
                    self.send_trade_email(
                        trade_type="Sell Yes Final",
                        price=yes_price,
                        amount=0.0,  # 卖出时金额为总持仓
                        trade_count=6
                    )

                    # 卖出了 YES 后卖 NO 点击Positions-Sell-No按钮
                    self.position_sell_no_button.invoke()
                    time.sleep(1)
                    # 点击Sell-卖出按钮
                    self.sell_profit_button.invoke()
                    # 等待3秒
                    time.sleep(3)

                    # 发送交易邮件 - 卖出NO
                    self.send_trade_email(
                        trade_type="Sell No Final",
                        price=0.0,
                        amount=0.0,  # 卖出时金额为总持仓
                        trade_count=8
                    )
                    # 将Yes6和No6价格设置为0.00 
                    yes6_price_entry.delete(0, tk.END)
                    yes6_price_entry.insert(0, "0.00")
                    no6_price_entry.delete(0, tk.END)
                    no6_price_entry.insert(0, "0.00")
                    
                    # 设置新的价格并重启监控
                    self.yes_price_entry.delete(0, tk.END)
                    self.yes_price_entry.insert(0, "0.53")
                    self.no_price_entry.delete(0, tk.END)
                    self.no_price_entry.insert(0, "0.53")
                    self.yes1_price_entry.delete(0, tk.END)
                    self.yes1_price_entry.insert(0, "0.00")
                    self.no1_price_entry.delete(0, tk.END)
                    self.no1_price_entry.insert(0, "0.00")
                    self.yes2_price_entry.delete(0, tk.END)
                    self.yes2_price_entry.insert(0, "0.00")
                    self.no2_price_entry.delete(0, tk.END)
                    self.no2_price_entry.insert(0, "0.00")
                    self.yes3_price_entry.delete(0, tk.END)
                    self.yes3_price_entry.insert(0, "0.00")
                    self.no3_price_entry.delete(0, tk.END)
                    self.no3_price_entry.insert(0, "0.00")
                    self.yes4_price_entry.delete(0, tk.END)
                    self.yes4_price_entry.insert(0, "0.00")
                    self.no4_price_entry.delete(0, tk.END)
                    self.no4_price_entry.insert(0, "0.00")
                    self.yes5_price_entry.delete(0, tk.END)
                    self.yes5_price_entry.insert(0, "0.00")
                    self.no5_price_entry.delete(0, tk.END)
                    self.no5_price_entry.insert(0, "0.00")         
                    
                    # 在所有操作完成后,优雅退出并重启
                    self.logger.info("准备重启程序...")
                    self.root.after(1000, self.restart_program)  # 1秒后重启            
        except Exception as e:
            self.logger.error(f"Sell_yes执行失败: {str(e)}")
            self.update_status(f"Sell_yes执行失败: {str(e)}")
        finally:
            self.is_trading = False

    def Sell_no(self):
        """当NO6价格等于实时No价格时自动卖出"""
        try:
            self.is_trading = True
            if not self.driver:
                raise Exception("浏览器连接丢失")   
            # 获取当前No价格
            prices = self.driver.execute_script("""
                function getPrices() {
                    const prices = {yes: null, no: null};
                    const elements = document.getElementsByTagName('span');
                    
                    for (let el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('No') && text.includes('¢')) {
                            const match = text.match(/(\\d+\\.?\\d*)¢/);
                            if (match) prices.no = parseFloat(match[1]);
                        }
                    }
                    return prices;
                }
                return getPrices();
            """)
                
            if prices['no'] is not None:
                no_price = float(prices['no']) / 100
                
                # 获取No6价格
                yes6_price_entry = self.yes_frame.grid_slaves(row=12, column=1)[0]
                no6_price_entry = self.no_frame.grid_slaves(row=12, column=1)[0]
                no6_target = float(no6_price_entry.get())
                
                # 检查No6价格匹配
                if abs(no6_target - no_price) < 0.0001 and no6_target > 0:
                    self.logger.info("No6价格匹配,执行自动卖出")
                    # 点击Positions-Sell-No按钮
                    self.position_sell_no_button.invoke()
                    time.sleep(0.5)
                    # 点击Sell-卖出按钮
                    self.sell_profit_button.invoke()
                    # 等待3秒
                    time.sleep(3)

                    # 发送交易邮件 - 卖出NO
                    self.send_trade_email(
                        trade_type="Sell No Final",
                        price=no_price,
                        amount=0.0,  # 卖出时金额为总持仓
                        trade_count=6
                    )
                    # 执行等待和刷新
                    self.sleep_refresh("Sell_no")
                    
                    # 卖完 NO 后卖 YES点击Positions-Sell-Yes按钮
                    self.position_sell_yes_button.invoke()
                    time.sleep(1)
                    # 点击Sell-卖出按钮
                    self.sell_profit_button.invoke()
                    # 等待3秒
                    time.sleep(3)
                    # 刷新页面
                    self.driver.refresh()

                    # 发送交易邮件 - 卖出YES
                    self.send_trade_email(
                        trade_type="Sell Yes Final",
                        price=0.0,
                        amount=0.0,  # 卖出时金额为总持仓
                        trade_count=8
                    )
                    # 将Yes6和No6价格设置为0.00
                    yes6_price_entry.delete(0, tk.END)
                    yes6_price_entry.insert(0, "0.00")
                    no6_price_entry.delete(0, tk.END) 
                    no6_price_entry.insert(0, "0.00")
                    
                    # 设置新的价格并重启监控
                    self.yes_price_entry.delete(0, tk.END)
                    self.yes_price_entry.insert(0, "0.53")
                    self.no_price_entry.delete(0, tk.END)
                    self.no_price_entry.insert(0, "0.53")
                    self.yes1_price_entry.delete(0, tk.END)
                    self.yes1_price_entry.insert(0, "0.00")
                    self.no1_price_entry.delete(0, tk.END)
                    self.no1_price_entry.insert(0, "0.00")
                    self.yes2_price_entry.delete(0, tk.END)
                    self.yes2_price_entry.insert(0, "0.00")
                    self.no2_price_entry.delete(0, tk.END)
                    self.no2_price_entry.insert(0, "0.00")
                    self.yes3_price_entry.delete(0, tk.END)
                    self.yes3_price_entry.insert(0, "0.00")
                    self.no3_price_entry.delete(0, tk.END)
                    self.no3_price_entry.insert(0, "0.00")
                    self.yes4_price_entry.delete(0, tk.END)
                    self.yes4_price_entry.insert(0, "0.00")
                    self.no4_price_entry.delete(0, tk.END)
                    self.no4_price_entry.insert(0, "0.00")
                    self.yes5_price_entry.delete(0, tk.END)
                    self.yes5_price_entry.insert(0, "0.00")
                    self.no5_price_entry.delete(0, tk.END)
                    self.no5_price_entry.insert(0, "0.00")
                    
                    # 在所有操作完成后,优雅退出并重启
                    self.logger.info("准备重启程序...")
                    self.root.after(1000, self.restart_program)  # 1秒后重启    
        except Exception as e:
            self.logger.error(f"Sell_no执行失败: {str(e)}")
            self.update_status(f"Sell_no执行失败: {str(e)}")
        finally:
            self.is_trading = False

    def send_trade_email(self, trade_type, price, amount, trade_count):
        """发送交易邮件"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                hostname = socket.gethostname()
                sender = 'huacaihuijin@126.com'
                receiver = 'huacaihuijin@126.com'
                app_password = 'YUwsXZ8SYSW6RcTf'  # 有效期 180 天，请及时更新，下次到期日 2025-06-29
                
                # 获取交易币对信息
                trading_pair = self.trading_pair_label.cget("text")
                if not trading_pair or trading_pair == "--":
                    trading_pair = "未知交易币对"
                
                msg = MIMEMultipart()
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                subject = f'{hostname}第{trade_count}次{trade_type}的{trading_pair}'
                msg['Subject'] = Header(subject, 'utf-8')
                msg['From'] = sender
                msg['To'] = receiver
                
                content = f"""
                交易账户: {hostname}
                交易币对: {trading_pair}
                交易类型: {trade_type}
                交易价格: ${price:.2f}
                交易金额: ${amount:.2f}
                交易时间: {current_time}
                当前总交易次数: {trade_count}
                """
                msg.attach(MIMEText(content, 'plain', 'utf-8'))
                
                self.logger.info(f"尝试发送邮件 (第{attempt + 1}次): {trade_type}")
                
                # 使用126.com的SMTP服务器
                server = smtplib.SMTP_SSL('smtp.126.com', 465, timeout=5)  # 使用SSL连接
                server.set_debuglevel(1)
                
                try:
                    server.login(sender, app_password)
                    server.sendmail(sender, receiver, msg.as_string())
                    self.logger.info(f"邮件发送成功: {trade_type}")
                    self.update_status(f"交易邮件发送成功: {trade_type}")
                    return  # 发送成功,退出重试循环
                except Exception as e:
                    self.logger.error(f"SMTP操作失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"等待 {retry_delay} 秒后重试...")
                        time.sleep(retry_delay)
                finally:
                    try:
                        server.quit()
                    except Exception:
                        pass          
            except Exception as e:
                self.logger.error(f"邮件准备失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)     
        # 所有重试都失败
        error_msg = f"发送邮件失败,已重试{max_retries}次"
        self.logger.error(error_msg)
        self.update_status(error_msg)

    def restart_program(self):
        """重启程序,保持浏览器打开"""
        try:
            self.logger.info("正在重启程序...")
            self.update_status("正在重启程序...")
            
            # 不关闭浏览器,只关闭GUI
            self.root.quit()
            
            # 使用subprocess启动新进程,添加--restart参数
            subprocess.Popen(['python3', 'crypto_trader.py', '--restart'])
            
            # 退出当前程序
            sys.exit(0)   
        except Exception as e:
            self.logger.error(f"重启程序失败: {str(e)}")
            self.update_status(f"重启程序失败: {str(e)}")

    def auto_start_monitor(self):
        """自动点击开始监控按钮"""
        try:
            self.logger.info("程序重启,自动开始监控...")
            self.start_button.invoke()  # 触发按钮点击事件
        except Exception as e:
            self.logger.error(f"自动开始监控失败: {str(e)}")
            self.update_status(f"自动开始监控失败: {str(e)}")

    def schedule_refresh(self):
        """实现每 5 分钟页面刷新一次"""
        if self.refresh_timer:
            self.root.after_cancel(self.refresh_timer)
        self.refresh_timer = self.root.after(self.refresh_interval, self.refresh_page)

    def refresh_page(self):
        """实现每 5 分钟刷新页面一次"""
        try:
            if not self.is_trading and self.driver:
                self.logger.info("执行定时页面刷新...")
                self.driver.refresh()
                self.logger.info("页面刷新完成")
            else:
                self.logger.info("正在交易中或浏览器未连接，跳过页面刷新")
        except Exception as e:
            self.logger.error(f"页面刷新失败: {str(e)}")
        finally:
            # 安排下一次刷新
            if self.running:
                self.schedule_refresh()

    def sleep_refresh(self, operation_name="未指定操作"):
        """
        执行等待3秒并刷新页面的操作，重复4次
        
        Args:
            operation_name (str): 操作名称,用于日志记录
        """
        try:
            for i in range(3):  # 重复4次，如果要重复 5 次，修改数字即可
                self.logger.info(f"{operation_name} - 等待3秒后刷新页面 ({i+1}/4)")
                time.sleep(6)  # 等待3秒
                self.driver.refresh()  # 刷新页面       
        except Exception as e:
            self.logger.error(f"{operation_name} - sleep_refresh操作失败: {str(e)}")

    def check_and_handle_login(self):
        """执行登录操作"""
        try:
            self.logger.info("开始执行登录操作...")
            
            # 点击登录按钮
            login_button = self.driver.find_element(By.XPATH, 
                '//*[@id="__pm_viewport"]/nav[1]/div[1]/div[3]/div/nav/div/ul/div[1]/div/button')
            login_button.click()
            time.sleep(1)
            
            # 使用 JavaScript 查找并点击 MetaMask 按钮
            self.driver.execute_script("""
                const buttons = document.querySelectorAll('button');
                for (const button of buttons) {
                    if (button.textContent.includes('MetaMask')) {
                        button.click();
                        break;
                    }
                }
            """)
            time.sleep(3)
            
            # 处理 MetaMask 弹窗
            # 模拟键盘操作序列
            # 1. 按5次TAB
            for _ in range(5):
                pyautogui.press('tab')
                time.sleep(0.1)  # 每次按键之间添加短暂延迟
            
            # 2. 按1次ENTER
            pyautogui.press('enter')
            time.sleep(2)  # 等待2秒
            
            # 3. 按7次TAB
            for _ in range(7):
                pyautogui.press('tab')
                time.sleep(0.1)
            
            # 4. 按1次ENTER
            pyautogui.press('enter')
            
            # 等待弹窗自动关闭
            time.sleep(0.3)
            
            self.logger.info("登录操作完成")
            return True
            
        except Exception as e:
            self.logger.error(f"登录操作失败: {str(e)}")
            return False

    
if __name__ == "__main__":
    try:
        app = CryptoTrader()
        app.run()
    except Exception as e:
        print(f"程序启动错误: {str(e)}")
        sys.exit(1) 
