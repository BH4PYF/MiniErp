/**
 * 移动端表单和数据展示组件
 * 包含表单验证、数据展示和交互优化
 */

// 移动端表单对象
const mobileForms = {
    // 初始化表单
    init() {
        this.initFormValidation();
        this.initFormSubmit();
        this.initDataDisplay();
        this.initDatePickers();
        this.initSelects();
    },

    // 初始化表单验证
    initFormValidation() {
        const forms = document.querySelectorAll('.mobile-form');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                    mobileApp.showMessage('请填写所有必填字段', 'warning');
                }
            });

            // 实时验证
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                input.addEventListener('blur', () => {
                    this.validateField(input);
                });
            });
        });
    },

    // 验证表单
    validateForm(form) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            if (!this.validateField(field)) {
                isValid = false;
            }
        });

        return isValid;
    },

    // 验证单个字段
    validateField(field) {
        const value = field.value.trim();
        const fieldName = field.dataset.name || field.name;

        // 移除之前的错误信息
        this.removeError(field);

        // 验证必填字段
        if (field.hasAttribute('required') && !value) {
            this.showError(field, `请输入${fieldName}`);
            return false;
        }

        // 验证邮箱
        if (field.type === 'email' && value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                this.showError(field, '请输入有效的邮箱地址');
                return false;
            }
        }

        // 验证手机号
        if (field.type === 'tel' && value) {
            const phoneRegex = /^1[3-9]\d{9}$/;
            if (!phoneRegex.test(value)) {
                this.showError(field, '请输入有效的手机号');
                return false;
            }
        }

        // 验证密码
        if (field.type === 'password' && value) {
            if (value.length < 6) {
                this.showError(field, '密码长度至少为6位');
                return false;
            }
        }

        // 验证数字
        if (field.type === 'number' && value) {
            if (isNaN(value)) {
                this.showError(field, '请输入有效的数字');
                return false;
            }
        }

        return true;
    },

    // 显示错误信息
    showError(field, message) {
        field.classList.add('is-invalid');

        // 检查是否已有错误信息元素
        let errorElement = field.nextElementSibling;
        if (errorElement && errorElement.classList.contains('invalid-feedback')) {
            errorElement.textContent = message;
        } else {
            // 创建新的错误信息元素
            errorElement = document.createElement('div');
            errorElement.className = 'invalid-feedback';
            errorElement.textContent = message;
            errorElement.style.cssText = `
                display: block;
                font-size: 12px;
                color: #dc3545;
                margin-top: 4px;
            `;
            field.parentNode.appendChild(errorElement);
        }
    },

    // 移除错误信息
    removeError(field) {
        field.classList.remove('is-invalid');

        const errorElement = field.nextElementSibling;
        if (errorElement && errorElement.classList.contains('invalid-feedback')) {
            errorElement.remove();
        }
    },

    // 初始化表单提交
    initFormSubmit() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                // 只处理POST表单
                if (form.method.toLowerCase() === 'post') {
                    const submitButton = form.querySelector('button[type="submit"]');
                    if (submitButton) {
                        // 显示加载状态
                        const originalText = submitButton.textContent;
                        submitButton.textContent = '提交中...';
                        submitButton.disabled = true;

                        // 保存原始文本，以便表单提交后恢复
                        submitButton.dataset.originalText = originalText;

                        // 显示全局加载状态
                        mobileApp.showLoading();
                    }
                }
            });
        });
    },

    // 初始化数据展示
    initDataDisplay() {
        // 初始化表格
        this.initTables();

        // 初始化列表
        this.initLists();

        // 初始化卡片
        this.initCards();
    },

    // 初始化表格
    initTables() {
        const tables = document.querySelectorAll('.mobile-table');
        tables.forEach(table => {
            // 处理表格行点击
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                if (row.dataset.href) {
                    row.classList.add('mobile-touchable');
                    row.addEventListener('click', () => {
                        window.location.href = row.dataset.href;
                    });
                }
            });
        });
    },

    // 初始化列表
    initLists() {
        const lists = document.querySelectorAll('.mobile-list');
        lists.forEach(list => {
            // 处理列表项点击
            const items = list.querySelectorAll('.mobile-list-item');
            items.forEach(item => {
                if (item.querySelector('a')) {
                    item.classList.add('mobile-touchable');
                }
            });
        });
    },

    // 初始化卡片
    initCards() {
        const cards = document.querySelectorAll('.mobile-card');
        cards.forEach(card => {
            // 处理卡片点击
            if (card.dataset.href) {
                card.classList.add('mobile-touchable');
                card.addEventListener('click', () => {
                    window.location.href = card.dataset.href;
                });
            }
        });
    },

    // 初始化日期选择器
    initDatePickers() {
        const dateInputs = document.querySelectorAll('input[type="date"]');
        dateInputs.forEach(input => {
            // 添加日期选择器样式
            input.classList.add('mobile-form-control');

            // 设置默认日期
            if (!input.value) {
                const today = new Date().toISOString().split('T')[0];
                input.value = today;
            }
        });
    },

    // 初始化选择框
    initSelects() {
        const selects = document.querySelectorAll('select');
        selects.forEach(select => {
            // 添加选择框样式
            select.classList.add('mobile-form-select');

            // 防止下拉框被手势事件影响
            select.addEventListener('touchstart', (e) => {
                e.stopPropagation();
            }, { passive: true });

            select.addEventListener('touchmove', (e) => {
                e.stopPropagation();
            }, { passive: true });

            select.addEventListener('touchend', (e) => {
                e.stopPropagation();
            }, { passive: true });
        });
    },

    // 提交表单
    submitForm(form) {
        if (this.validateForm(form)) {
            form.submit();
        } else {
            mobileApp.showMessage('请检查表单填写是否正确', 'warning');
        }
    },

    // 重置表单
    resetForm(form) {
        form.reset();
        const errorElements = form.querySelectorAll('.invalid-feedback');
        errorElements.forEach(element => {
            element.remove();
        });
        const invalidFields = form.querySelectorAll('.is-invalid');
        invalidFields.forEach(field => {
            field.classList.remove('is-invalid');
        });
    },

    // 获取表单数据
    getFormData(form) {
        const formData = {};
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (input.name) {
                formData[input.name] = input.value;
            }
        });
        return formData;
    },

    // 设置表单数据
    setFormData(form, data) {
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (input.name && data[input.name] !== undefined) {
                input.value = data[input.name];
            }
        });
    }
};

// 导出模块
if (typeof window !== 'undefined') {
    window.mobileForms = mobileForms;
    window.addEventListener('DOMContentLoaded', () => {
        mobileForms.init();
    });
}
