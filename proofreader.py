#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LM Studio 文本校对工具
使用本地LM Studio大语言模型对Markdown文件进行智能校对
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import requests
import json
import threading
from datetime import datetime

# 尝试导入GPUtil，如果失败则设为None
try:
    import GPUtil
    HAS_GPUtil = True
except ImportError:
    HAS_GPUtil = False


class ProofreaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LM Studio 文本校对工具")
        self.root.geometry("900x750")
        self.root.resizable(True, True)

        # 配置
        self.ip_var = tk.StringVar(value="http://127.0.0.1:1234/v1")
        self.temperature_var = tk.StringVar(value="0.3")
        self.max_tokens_var = tk.StringVar(value="131072")
        self.prompt_var = tk.StringVar()
        self.save_path_var = tk.StringVar()
        self.use_same_dir = tk.BooleanVar(value=True)
        self.selected_files = []
        self.selected_model = tk.StringVar()
        self.is_connected = False
        self.model_list = []

        # 默认提示词模板
        self.default_prompt = """你是一个专业的文本校对助手。请处理我提供的文本，要求如下：
1. 删除所有无意义的标记字符，例如 <|zh|>、<|HAPPY|>、<|BGM|>、<|withitn|> 等类似格式的无效内容。
2. 对文本进行适当分段，根据语义和逻辑将冗长的段落拆分成易于阅读的短段落。
3. 格式化文本，确保每个段落的段首空两行。
4. 请直接输出处理后的最终文本，不要有任何解释、说明或开场白。"""

        self.prompt_var.set(self.default_prompt)

        # 颜色配置
        self.colors = {
            'primary': '#2563EB',
            'secondary': '#1E40AF',
            'success': '#10B981',
            'warning': '#F59E0B',
            'error': '#EF4444',
            'bg': '#F8FAFC',
            'card': '#FFFFFF',
            'text': '#1E293B',
            'text_secondary': '#64748B',
            'border': '#E2E8F0'
        }

        # 字体配置
        self.fonts = {
            'title': ('Microsoft YaHei', 16, 'bold'),
            'section': ('Microsoft YaHei', 11, 'bold'),
            'body': ('Microsoft YaHei', 10),
            'secondary': ('Microsoft YaHei', 9),
            'log': ('Consolas', 9)
        }

        self.create_widgets()
        self.load_gpu_info()

    def create_widgets(self):
        """创建所有组件"""
        # 主容器
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # 标题
        title_label = tk.Label(main_container, text="文本校对工具 by EASON",
                              font=self.fonts['title'],
                              fg=self.colors['primary'], bg=self.colors['bg'])
        title_label.pack(pady=(0, 16))

        # 创建卡片式布局
        # 1. 文件选择区域
        self.create_file_section(main_container)

        # 2. LM Studio 连接区域
        self.create_connection_section(main_container)

        # 3. 提示词模板区域
        self.create_prompt_section(main_container)

        # 4. 日志区域
        self.create_log_section(main_container)

        # 5. GPU 信息区域
        self.create_gpu_section(main_container)

    def create_card(self, parent):
        """创建卡片容器"""
        card = tk.Frame(parent, bg=self.colors['card'], relief=tk.FLAT,
                        highlightbackground=self.colors['border'],
                        highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 12))
        return card

    def create_file_section(self, parent):
        """文件选择区域"""
        card = self.create_card(parent)

        # 标题
        header = tk.Frame(card, bg=self.colors['card'])
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        tk.Label(header, text="文件选择", font=self.fonts['section'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        # 文件选择区域 - 左边按钮 + 右边文件显示
        content_frame = tk.Frame(card, bg=self.colors['card'])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        # 左侧：文件选择按钮（一上一下）
        left_frame = tk.Frame(content_frame, bg=self.colors['card'])
        left_frame.pack(side=tk.LEFT, padx=(0, 16))

        tk.Button(left_frame, text="选择文件", command=self.select_files,
                 bg=self.colors['primary'], fg='white', font=self.fonts['body'],
                 relief=tk.FLAT, padx=16, pady=6).pack(fill=tk.X, pady=(0, 8))

        tk.Button(left_frame, text="选择文件夹", command=self.select_folder,
                 bg=self.colors['secondary'], fg='white', font=self.fonts['body'],
                 relief=tk.FLAT, padx=16, pady=6).pack(fill=tk.X)

        # 右侧：已选文件显示
        right_frame = tk.Frame(content_frame, bg=self.colors['card'])
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.file_label = tk.Label(right_frame, text="未选择任何文件",
                                   font=self.fonts['secondary'], fg=self.colors['text_secondary'],
                                   bg=self.colors['card'], anchor='nw', justify=tk.LEFT,
                                   wraplength=500, height=3)
        self.file_label.pack(fill=tk.BOTH, expand=True, padx=(8, 0))

        # 保存位置设置 - 一行水平显示
        save_frame = tk.Frame(card, bg=self.colors['card'])
        save_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        tk.Checkbutton(save_frame, text="保存到源文件相同目录",
                      variable=self.use_same_dir,
                      bg=self.colors['card'], font=self.fonts['secondary'],
                      command=self.on_save_dir_toggle).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(save_frame, text="指定保存位置", command=self.select_save_dir,
                 bg=self.colors['text_secondary'], fg='white', font=self.fonts['secondary'],
                 relief=tk.FLAT, padx=12, pady=4).pack(side=tk.LEFT, padx=(0, 8))

        self.save_path_entry = tk.Entry(save_frame, textvariable=self.save_path_var,
                                        font=self.fonts['secondary'], state='disabled')
        self.save_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 开始处理按钮
        btn_frame = tk.Frame(card, bg=self.colors['card'])
        btn_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        self.start_btn = tk.Button(btn_frame, text="开始校对", command=self.start_processing,
                                  bg=self.colors['success'], fg='white',
                                  font=('Microsoft YaHei', 11, 'bold'),
                                  relief=tk.FLAT, padx=24, pady=8)
        self.start_btn.pack(side=tk.LEFT)

        self.progress_label = tk.Label(btn_frame, text="",
                                       font=self.fonts['secondary'],
                                       fg=self.colors['text_secondary'], bg=self.colors['card'])
        self.progress_label.pack(side=tk.RIGHT)


    def create_connection_section(self, parent):
        """连接设置区域"""
        card = self.create_card(parent)

        header = tk.Frame(card, bg=self.colors['card'])
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        tk.Label(header, text="LM Studio 连接", font=self.fonts['section'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        # IP地址设置 + 连接状态 - 一行水平显示
        top_row = tk.Frame(card, bg=self.colors['card'])
        top_row.pack(fill=tk.X, padx=16, pady=(0, 8))

        # IP地址设置
        tk.Label(top_row, text="API 地址:", font=self.fonts['body'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(top_row, textvariable=self.ip_var,
                                 font=self.fonts['body'], width=40)
        self.ip_entry.pack(side=tk.LEFT, padx=(8, 16), fill=tk.X, expand=True)

        # 连接状态
        tk.Button(top_row, text="检测连接", command=self.check_connection,
                 bg=self.colors['primary'], fg='white', font=self.fonts['body'],
                 relief=tk.FLAT, padx=16, pady=6).pack(side=tk.LEFT, padx=(0, 8))

        self.status_label = tk.Label(top_row, text="未检测",
                                     bg=self.colors['card'], fg=self.colors['text_secondary'],
                                     font=self.fonts['body'])
        self.status_label.pack(side=tk.LEFT, padx=(0, 8))

        self.status_indicator = tk.Label(top_row, text="●",
                                        bg=self.colors['card'], fg=self.colors['text_secondary'],
                                        font=('Microsoft YaHei', 14))
        self.status_indicator.pack(side=tk.LEFT)

        # 模型选择
        model_frame = tk.Frame(card, bg=self.colors['card'])
        model_frame.pack(fill=tk.X, padx=16, pady=(0, 8))

        tk.Label(model_frame, text="选择模型:", font=self.fonts['body'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        self.model_combo = ttk.Combobox(model_frame, textvariable=self.selected_model,
                                         font=self.fonts['body'], width=40,
                                         state='readonly')
        self.model_combo.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        tk.Button(model_frame, text="刷新模型", command=self.refresh_models,
                 bg=self.colors['secondary'], fg='white', font=self.fonts['secondary'],
                 relief=tk.FLAT, padx=12, pady=4).pack(side=tk.LEFT, padx=(8, 0))

        # 参数设置
        params_frame = tk.Frame(card, bg=self.colors['card'])
        params_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        # Temperature 设置
        temp_frame = tk.Frame(params_frame, bg=self.colors['card'])
        temp_frame.pack(side=tk.LEFT, padx=(0, 24))

        tk.Label(temp_frame, text="Temperature:", font=self.fonts['body'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        self.temp_entry = tk.Entry(temp_frame, textvariable=self.temperature_var,
                                   font=self.fonts['body'], width=8)
        self.temp_entry.pack(side=tk.LEFT, padx=(4, 0))

        tk.Label(temp_frame, text="(0.0-2.0)", font=self.fonts['secondary'],
                fg=self.colors['text_secondary'], bg=self.colors['card']).pack(side=tk.LEFT, padx=(4, 0))

        # Max Tokens 设置
        tokens_frame = tk.Frame(params_frame, bg=self.colors['card'])
        tokens_frame.pack(side=tk.LEFT)

        tk.Label(tokens_frame, text="Max Tokens:", font=self.fonts['body'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        self.tokens_entry = tk.Entry(tokens_frame, textvariable=self.max_tokens_var,
                                     font=self.fonts['body'], width=10)
        self.tokens_entry.pack(side=tk.LEFT, padx=(4, 0))

        tk.Label(tokens_frame, text="(最大输出长度)", font=self.fonts['secondary'],
                fg=self.colors['text_secondary'], bg=self.colors['card']).pack(side=tk.LEFT, padx=(4, 0))

    def create_prompt_section(self, parent):
        """提示词模板区域"""
        card = self.create_card(parent)

        header = tk.Frame(card, bg=self.colors['card'])
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        tk.Label(header, text="校对提示词模板", font=self.fonts['section'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        # 提示词文本框
        self.prompt_text = scrolledtext.ScrolledText(card, font=self.fonts['secondary'],
                                                     height=6, wrap=tk.WORD,
                                                     relief=tk.FLAT,
                                                     highlightbackground=self.colors['border'],
                                                     highlightthickness=1)
        self.prompt_text.insert('1.0', self.default_prompt)
        self.prompt_text.pack(fill=tk.X, padx=16, pady=(0, 12))

        # 恢复默认按钮
        tk.Button(card, text="恢复默认模板", command=self.reset_prompt,
                 bg=self.colors['text_secondary'], fg='white', font=self.fonts['secondary'],
                 relief=tk.FLAT, padx=12, pady=4).pack(anchor='e', padx=16, pady=(0, 12))

    def create_log_section(self, parent):
        """日志区域"""
        card = self.create_card(parent)

        header = tk.Frame(card, bg=self.colors['card'])
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        tk.Label(header, text="处理日志", font=self.fonts['section'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(card, font=self.fonts['log'],
                                                   height=10, wrap=tk.WORD,
                                                   relief=tk.FLAT, state='disabled',
                                                   bg='#1E1E1E', fg='#D4D4D4',
                                                   insertbackground='white')
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        # 配置标签颜色
        self.log_text.tag_config('info', foreground='#D4D4D4')
        self.log_text.tag_config('success', foreground='#4EC9B0')
        self.log_text.tag_config('error', foreground='#F48771')
        self.log_text.tag_config('warning', foreground='#CCA700')
        self.log_text.tag_config('time', foreground='#808080')

        
    def create_gpu_section(self, parent):
        """GPU信息区域"""
        card = self.create_card(parent)

        header = tk.Frame(card, bg=self.colors['card'])
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        tk.Label(header, text="GPU 信息", font=self.fonts['section'],
                fg=self.colors['text'], bg=self.colors['card']).pack(side=tk.LEFT)

        # GPU信息标签
        self.gpu_label = tk.Label(card, text="正在检测GPU...",
                                  font=self.fonts['secondary'],
                                  fg=self.colors['text_secondary'], bg=self.colors['card'],
                                  anchor='w', justify=tk.LEFT)
        self.gpu_label.pack(fill=tk.X, padx=16, pady=(0, 12))

        # 启动GPU信息自动更新（每5秒）
        self.update_gpu_info()

    def update_gpu_info(self):
        """更新GPU信息"""
        if not HAS_GPUtil:
            self.gpu_label.config(text="GPUtil未安装 (pip install GPUtil)", fg=self.colors['text_secondary'])
            return

        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                # 计算显存使用百分比
                usage_percent = (gpu.memoryUsed / gpu.memoryTotal) * 100 if gpu.memoryTotal > 0 else 0
                gpu_info = f"GPU: {gpu.name} | 显存: {gpu.memoryTotal}MB (已用: {gpu.memoryUsed}MB, {usage_percent:.1f}% | 可用: {gpu.memoryFree}MB)"
                self.gpu_label.config(text=gpu_info, fg=self.colors['text'])
            else:
                self.gpu_label.config(text="未检测到独立GPU (使用CPU)", fg=self.colors['text_secondary'])
        except Exception as e:
            self.gpu_label.config(text="GPU信息获取失败", fg=self.colors['warning'])

        # 每5秒自动更新一次
        self.root.after(5000, self.update_gpu_info)

    def load_gpu_info(self):
        """加载GPU信息（兼容旧调用）"""
        self.update_gpu_info()

    def select_files(self):
        """选择文件"""
        files = filedialog.askopenfilenames(
            title="选择需要校对的文件",
            filetypes=[("Markdown文件", "*.md"), ("所有文件", "*.*")]
        )
        if files:
            self.selected_files = list(files)
            self.log(f"已选择 {len(files)} 个文件", 'info')
            self.update_file_label()

    def select_folder(self):
        """选择文件夹"""
        folder = filedialog.askdirectory(title="选择包含Markdown文件的文件夹")
        if folder:
            md_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.endswith('.md'):
                        md_files.append(os.path.join(root, file))

            self.selected_files = md_files
            self.log(f"已选择文件夹: {folder}", 'info')
            self.log(f"找到 {len(md_files)} 个Markdown文件", 'info')
            self.update_file_label()

    def update_file_label(self):
        """更新文件显示"""
        if not self.selected_files:
            self.file_label.config(text="未选择任何文件")
            return

        if len(self.selected_files) == 1:
            self.file_label.config(text=f"已选择: {self.selected_files[0]}")
        else:
            self.file_label.config(text=f"已选择 {len(self.selected_files)} 个文件\n" +
                                  "\n".join(self.selected_files[:5]) +
                                  (f"\n... 还有 {len(self.selected_files) - 5} 个文件" if len(self.selected_files) > 5 else ""))

    def on_save_dir_toggle(self):
        """保存目录切换"""
        if self.use_same_dir.get():
            self.save_path_entry.config(state='disabled')
            self.save_path_var.set("")
        else:
            self.save_path_entry.config(state='normal')

    def select_save_dir(self):
        """选择保存目录"""
        folder = filedialog.askdirectory(title="选择保存位置")
        if folder:
            self.save_path_var.set(folder)
            self.use_same_dir.set(False)
            self.save_path_entry.config(state='normal')

    def reset_prompt(self):
        """恢复默认提示词"""
        self.prompt_text.delete('1.0', tk.END)
        self.prompt_text.insert('1.0', self.default_prompt)
        self.log("提示词已恢复为默认值", 'info')

    def log(self, message, level='info'):
        """添加日志"""
        self.log_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")

        # 根据语言设置标签
        if level == 'info':
            prefix = "[INFO]"
        elif level == 'success':
            prefix = "[SUCCESS]"
        elif level == 'error':
            prefix = "[ERROR]"
        elif level == 'warning':
            prefix = "[WARNING]"
        else:
            prefix = "[LOG]"

        self.log_text.insert(tk.END, f"[{timestamp}] ", 'time')
        self.log_text.insert(tk.END, f"{prefix} ", level)
        self.log_text.insert(tk.END, f"{message}\n", level)

        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def check_connection(self):
        """检测连接"""
        ip = self.ip_var.get().strip()
        if not ip:
            self.log("请输入API地址", 'error')
            return

        self.log(f"正在连接 {ip}...", 'info')

        try:
            # 添加 /v1/models 后缀
            if not ip.endswith('/v1'):
                base_url = ip.rstrip('/')
            else:
                base_url = ip.rstrip('/v1').rstrip('/')

            url = f"{base_url}/v1/models"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                self.is_connected = True
                self.status_label.config(text="已连接", fg=self.colors['success'])
                self.status_indicator.config(fg=self.colors['success'])
                self.log("连接成功!", 'success')

                # 解析模型列表
                try:
                    data = response.json()
                    models = data.get('data', [])
                    self.model_list = [m.get('id', 'unknown') for m in models]

                    if self.model_list:
                        self.model_combo['values'] = self.model_list
                        self.selected_model.set(self.model_list[0])
                        self.log(f"找到 {len(self.model_list)} 个模型", 'success')
                        for model in self.model_list:
                            self.log(f"  - {model}", 'info')
                    else:
                        self.log("未找到可用模型", 'warning')

                except json.JSONDecodeError:
                    self.log("模型列表解析失败", 'warning')

            else:
                self.is_connected = False
                self.status_label.config(text=f"连接失败 ({response.status_code})", fg=self.colors['error'])
                self.status_indicator.config(fg=self.colors['error'])
                self.log(f"连接失败: HTTP {response.status_code}", 'error')

        except requests.exceptions.Timeout:
            self.is_connected = False
            self.status_label.config(text="连接超时", fg=self.colors['error'])
            self.status_indicator.config(fg=self.colors['error'])
            self.log("连接超时，请检查LM Studio是否运行", 'error')

        except requests.exceptions.ConnectionError:
            self.is_connected = False
            self.status_label.config(text="无法连接", fg=self.colors['error'])
            self.status_indicator.config(fg=self.colors['error'])
            self.log("无法连接到服务器，请检查LM Studio是否运行", 'error')

        except Exception as e:
            self.is_connected = False
            self.status_label.config(text=f"错误: {str(e)}", fg=self.colors['error'])
            self.status_indicator.config(fg=self.colors['error'])
            self.log(f"连接错误: {str(e)}", 'error')

    def refresh_models(self):
        """刷新模型列表"""
        self.check_connection()

    def get_output_path(self, input_path):
        """获取输出路径"""
        if self.use_same_dir.get():
            base, ext = os.path.splitext(input_path)
            return f"{base}-已校对{ext}"
        else:
            folder = self.save_path_var.get()
            filename = os.path.basename(input_path)
            base, ext = os.path.splitext(filename)
            return os.path.join(folder, f"{base}-已校对{ext}")

    def process_file(self, file_path):
        """处理单个文件"""
        try:
            self.log(f"正在处理: {file_path}", 'info')

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                self.log(f"文件为空，跳过: {file_path}", 'warning')
                return False

            # 估算token数量并提示
            estimated_tokens = len(content) // 4  # 粗略估算
            self.log(f"文件长度: {len(content)} 字符, 估算约 {estimated_tokens} tokens", 'info')

            # 获取提示词
            prompt_template = self.prompt_text.get('1.0', tk.END).strip()
            full_prompt = f"{prompt_template}\n\n待校对文本：\n{content}"

            # API调用
            ip = self.ip_var.get().strip().rstrip('/')
            url = f"{ip}/chat/completions"

            model_name = self.selected_model.get()
            if not model_name:
                self.log("请先选择一个模型", 'error')
                return False

            # 获取用户设置的参数
            try:
                temperature = float(self.temperature_var.get())
                temperature = max(0.0, min(2.0, temperature))  # 限制在0-2之间
            except ValueError:
                temperature = 0.3
                self.log("Temperature 值无效，使用默认值 0.3", 'warning')

            try:
                max_tokens = int(self.max_tokens_var.get())
                max_tokens = max(1, min(131072, max_tokens))  # 限制在1-131072之间
            except ValueError:
                max_tokens = 131072
                self.log("Max Tokens 值无效，使用默认值 131072", 'warning')

            self.log(f"Temperature: {temperature}, Max Tokens: {max_tokens}", 'info')

            # 根据内容长度动态设置超时时间
            # 基本超时 120秒 + 每1000字符增加30秒 + 每1000 tokens增加60秒
            timeout_seconds = max(600, 120 + (len(content) // 1000) * 30 + (max_tokens // 1000) * 60)
            self.log(f"请求超时设置: {timeout_seconds}秒", 'info')

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": full_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True  # 启用流式输出
            }

            headers = {
                "Content-Type": "application/json"
            }

            self.log("正在等待模型响应...", 'info')

            # 重试机制 - 使用流式请求
            full_content = ""
            last_update_time = datetime.now()

            for attempt in range(3):
                try:
                    response = requests.post(url, json=payload, headers=headers,
                                            timeout=timeout_seconds, stream=True)

                    if response.status_code == 200:
                        # 处理流式响应
                        for line in response.iter_lines():
                            if line:
                                line_text = line.decode('utf-8')
                                if line_text.startswith('data: '):
                                    data_str = line_text[6:]  # 去掉 "data: " 前缀
                                    if data_str == '[DONE]':
                                        break
                                    try:
                                        data = json.loads(data_str)
                                        if 'choices' in data:
                                            delta = data['choices'][0].get('delta', {})
                                            if 'content' in delta:
                                                full_content += delta['content']
                                                # 每秒更新一次日志
                                                now = datetime.now()
                                                if (now - last_update_time).total_seconds() >= 2:
                                                    self.log(f"已生成 {len(full_content)} 字符...", 'info')
                                                    last_update_time = now
                                    except json.JSONDecodeError:
                                        continue

                        self.log(f"模型响应完成, 共 {len(full_content)} 字符", 'success')
                        break
                    else:
                        self.log(f"API错误: HTTP {response.status_code}", 'error')
                        try:
                            error_detail = response.json()
                            self.log(f"错误详情: {error_detail}", 'error')
                        except:
                            pass
                        return False

                except requests.exceptions.Timeout:
                    if attempt < 2:
                        self.log(f"请求超时，重试 ({attempt + 1}/3)...", 'warning')
                    else:
                        self.log(f"文件处理失败: 请求超时 (超过 {timeout_seconds} 秒)", 'error')
                        self.log("提示: 请选择较短的文本文件，或等待LM Studio模型加载完成", 'warning')
                        return False
                except requests.exceptions.ConnectionError:
                    self.log("连接中断，请检查LM Studio是否正常运行", 'error')
                    return False

            # 如果有收集到的内容，保存它
            if full_content:
                output_path = self.get_output_path(file_path)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(full_content)
                self.log(f"处理完成: {output_path}", 'success')
                return True
            else:
                self.log("未能获取模型响应内容", 'error')
                return False

        except FileNotFoundError:
            self.log(f"文件未找到: {file_path}", 'error')
            return False
        except PermissionError:
            self.log(f"权限错误: {file_path}", 'error')
            return False
        except Exception as e:
            self.log(f"处理错误: {str(e)}", 'error')
            return False

    def start_processing(self):
        """开始处理"""
        if not self.selected_files:
            messagebox.showwarning("提示", "请先选择需要校对的文件或文件夹")
            return

        if not self.is_connected:
            messagebox.showwarning("提示", "请先检测并确认LM Studio已连接")
            return

        if not self.selected_model.get():
            messagebox.showwarning("提示", "请选择一个模型")
            return

        # 禁用开始按钮
        self.start_btn.config(state='disabled', text="处理中...")
        self.progress_label.config(text="")

        # 在新线程中处理
        thread = threading.Thread(target=self._process_files_thread)
        thread.daemon = True
        thread.start()

    def _process_files_thread(self):
        """处理文件线程"""
        total = len(self.selected_files)
        success = 0

        self.log("=" * 50, 'info')
        self.log(f"开始处理 {total} 个文件", 'info')
        self.log("=" * 50, 'info')

        for i, file_path in enumerate(self.selected_files, 1):
            self.root.after(0, lambda i=i, t=total: self.progress_label.config(text=f"进度: {i}/{t}"))
            if self.process_file(file_path):
                success += 1

        self.root.after(0, self._processing_complete, total, success)

    def _processing_complete(self, total, success):
        """处理完成"""
        self.start_btn.config(state='normal', text="开始校对")
        self.progress_label.config(text="")

        self.log("=" * 50, 'info')
        self.log(f"处理完成! 成功: {success}/{total}", 'success' if success == total else 'warning')
        self.log("=" * 50, 'info')

        messagebox.showinfo("完成", f"处理完成!\n成功: {success}/{total}\n失败: {total - success}/{total}")


def main():
    """主函数"""
    root = tk.Tk()

    # 设置窗口图标（如果有的话）
    try:
        root.iconbitmap('icon.ico')
    except:
        pass

    app = ProofreaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
