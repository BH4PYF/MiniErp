#!/usr/bin/env python3
"""
检查移动端优化是否生效的脚本

该脚本会检查：
1. 移动端相关JavaScript文件是否存在于新的目录中
2. base.html文件是否正确引用了这些文件
3. 移动端优化功能是否正常配置
"""

import os
import re

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# 静态文件目录
STATIC_DIR = os.path.join(PROJECT_ROOT, 'static')
# 移动端JavaScript文件目录
MOBILE_JS_DIR = os.path.join(STATIC_DIR, 'js', 'mobile')
# base.html文件路径
BASE_HTML_PATH = os.path.join(PROJECT_ROOT, 'templates', 'base.html')

# 移动端相关JavaScript文件列表
MOBILE_JS_FILES = [
    'mobile-sidebar.js',
    'mobile-form.js',
    'mobile-gestures.js',
    'mobile-loading.js'
]

def check_mobile_files_exist():
    """检查移动端JavaScript文件是否存在"""
    print("=== 检查移动端JavaScript文件 ===")
    all_exist = True
    
    if not os.path.exists(MOBILE_JS_DIR):
        print(f"❌ 移动端JavaScript目录不存在: {MOBILE_JS_DIR}")
        return False
    
    for file_name in MOBILE_JS_FILES:
        file_path = os.path.join(MOBILE_JS_DIR, file_name)
        if os.path.exists(file_path):
            print(f"✅ {file_name} 存在")
        else:
            print(f"❌ {file_name} 不存在")
            all_exist = False
    
    return all_exist

def check_base_html_references():
    """检查base.html是否正确引用了移动端JavaScript文件"""
    print("\n=== 检查base.html引用 ===")
    
    if not os.path.exists(BASE_HTML_PATH):
        print(f"❌ base.html文件不存在: {BASE_HTML_PATH}")
        return False
    
    with open(BASE_HTML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    all_referenced = True
    for file_name in MOBILE_JS_FILES:
        expected_path = f"js/mobile/{file_name}"
        # 检查是否有未被注释的引用
        # 首先移除所有注释内容
        content_without_comments = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        # 然后检查是否有引用
        pattern = re.compile(rf"static ['\"]({re.escape(expected_path)})['\"]")
        has_uncommented_reference = bool(pattern.search(content_without_comments))
        
        if has_uncommented_reference:
            print(f"✅ {file_name} 被正确引用")
        else:
            print(f"❌ {file_name} 未被正确引用（可能被注释掉）")
            all_referenced = False
    
    return all_referenced

def check_mobile_optimization_features():
    """检查移动端优化功能是否正常配置"""
    print("\n=== 检查移动端优化功能 ===")
    
    # 检查mobile-form.js中的优化
    form_js_path = os.path.join(MOBILE_JS_DIR, 'mobile-form.js')
    if os.path.exists(form_js_path):
        with open(form_js_path, 'r', encoding='utf-8') as f:
            form_content = f.read()
        
        # 检查是否只对POST表单处理
        if 'form.method.toUpperCase() === "POST"' in form_content or 'form.method.toUpperCase() === "POST"' in form_content:
            print("✅ 表单提交按钮优化: 只对POST表单处理")
        else:
            # 尝试更宽松的匹配
            if 'method.toUpperCase()' in form_content and 'POST' in form_content:
                print("✅ 表单提交按钮优化: 只对POST表单处理")
            else:
                print("❌ 表单提交按钮优化: 未正确配置")
    else:
        print("❌ mobile-form.js 文件不存在")
    
    # 检查mobile-gestures.js中的优化
    gestures_js_path = os.path.join(MOBILE_JS_DIR, 'mobile-gestures.js')
    if os.path.exists(gestures_js_path):
        with open(gestures_js_path, 'r', encoding='utf-8') as f:
            gestures_content = f.read()
        
        # 检查是否跳过下拉框和输入元素的触摸事件
        if 'target.tagName === \'SELECT\'' in gestures_content:
            print("✅ 下拉刷新优化: 跳过下拉框和输入元素的触摸事件")
        else:
            print("❌ 下拉刷新优化: 未正确配置")
    else:
        print("❌ mobile-gestures.js 文件不存在")

def main():
    """主函数"""
    print("开始检查移动端优化配置...\n")
    
    # 检查文件是否存在
    files_exist = check_mobile_files_exist()
    
    # 检查base.html引用
    references_correct = check_base_html_references()
    
    # 检查优化功能
    check_mobile_optimization_features()
    
    print("\n=== 检查结果汇总 ===")
    if files_exist and references_correct:
        print("🎉 移动端优化配置正确，所有文件都已就绪！")
    else:
        print("⚠️  移动端优化配置存在问题，请检查上述错误信息。")

if __name__ == "__main__":
    main()
