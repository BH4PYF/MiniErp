document.addEventListener('DOMContentLoaded', function() {
    // 表单自动填充优化
    optimizeFormAutofill();
    
    // 表单验证增强
    enhanceFormValidation();
    
    // 移动端键盘优化
    optimizeKeyboardBehavior();
    
    // 表单提交按钮优化
    optimizeSubmitButtons();
});

// 表单自动填充优化
function optimizeFormAutofill() {
    // 为表单字段添加适当的autocomplete属性
    const formFields = document.querySelectorAll('input, select, textarea');
    formFields.forEach(field => {
        const name = field.name.toLowerCase();
        const id = field.id.toLowerCase();
        
        // 根据字段名称自动设置autocomplete属性
        if (name.includes('name') || id.includes('name')) {
            field.setAttribute('autocomplete', 'name');
        } else if (name.includes('email') || id.includes('email')) {
            field.setAttribute('autocomplete', 'email');
        } else if (name.includes('phone') || id.includes('phone')) {
            field.setAttribute('autocomplete', 'tel');
        } else if (name.includes('address') || id.includes('address')) {
            field.setAttribute('autocomplete', 'address');
        } else if (name.includes('city') || id.includes('city')) {
            field.setAttribute('autocomplete', 'address-level2');
        } else if (name.includes('province') || id.includes('province')) {
            field.setAttribute('autocomplete', 'address-level1');
        } else if (name.includes('zip') || id.includes('zip')) {
            field.setAttribute('autocomplete', 'postal-code');
        } else if (name.includes('username') || id.includes('username')) {
            field.setAttribute('autocomplete', 'username');
        } else if (name.includes('password') || id.includes('password')) {
            field.setAttribute('autocomplete', 'current-password');
        } else if (name.includes('price') || id.includes('price') || 
                   name.includes('cost') || id.includes('cost') ||
                   name.includes('amount') || id.includes('amount')) {
            field.setAttribute('inputmode', 'decimal');
            field.setAttribute('pattern', '[0-9]*[.,]?[0-9]+');
        } else if (name.includes('number') || id.includes('number') ||
                   name.includes('qty') || id.includes('qty') ||
                   name.includes('quantity') || id.includes('quantity')) {
            field.setAttribute('inputmode', 'numeric');
            field.setAttribute('pattern', '[0-9]*');
        }
    });
}

// 表单验证增强
function enhanceFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!this.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
                
                // 滚动到第一个无效字段
                const firstInvalid = this.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus();
                }
            }
            this.classList.add('was-validated');
        }, false);
        
        // 实时验证
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
            
            // 失去焦点时验证
            input.addEventListener('blur', function() {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
        });
    });
}

// 移动端键盘优化
function optimizeKeyboardBehavior() {
    // 防止键盘弹出时页面缩放
    document.addEventListener('touchstart', function(e) {
        const target = e.target;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
            // 防止双击缩放
            target.style.touchAction = 'manipulation';
        }
    });
    
    // 键盘弹出时调整页面
    window.addEventListener('resize', function() {
        const activeElement = document.activeElement;
        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
            setTimeout(() => {
                activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 100);
        }
    });
    
    // 点击页面空白处关闭键盘
    document.addEventListener('click', function(e) {
        const target = e.target;
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA' && 
            !target.closest('input') && !target.closest('textarea')) {
            document.activeElement.blur();
        }
    });
}

// 表单提交按钮优化
function optimizeSubmitButtons() {
    const submitButtons = document.querySelectorAll('button[type="submit"], input[type="submit"]');
    submitButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 只对POST表单进行处理，GET表单会直接跳转
            const form = this.closest('form');
            if (form && form.method.toUpperCase() === 'POST') {
                // 防止重复提交
                if (!this.classList.contains('submitting')) {
                    this.classList.add('submitting');
                    this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> 提交中...';
                    this.disabled = true;
                    
                    // 30秒后恢复按钮状态（防止网络问题导致按钮一直禁用）
                    setTimeout(() => {
                        if (this.classList.contains('submitting')) {
                            this.classList.remove('submitting');
                            this.innerHTML = this.dataset.originalText || '提交';
                            this.disabled = false;
                        }
                    }, 30000);
                }
            }
        });
        
        // 保存原始按钮文本
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.innerHTML;
        }
    });
}

// 数字输入框优化
function optimizeNumberInputs() {
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        // 防止上下箭头改变值
        input.addEventListener('wheel', function(e) {
            e.preventDefault();
        });
        
        // 输入时格式化数字
        input.addEventListener('input', function() {
            let value = this.value;
            // 移除除数字和小数点外的所有字符
            value = value.replace(/[^0-9.]/g, '');
            // 确保只有一个小数点
            const parts = value.split('.');
            if (parts.length > 2) {
                value = parts[0] + '.' + parts.slice(1).join('');
            }
            // 限制小数位数
            if (parts.length === 2 && parts[1].length > 2) {
                value = parts[0] + '.' + parts[1].slice(0, 2);
            }
            this.value = value;
        });
    });
}

// 日期选择器优化
function optimizeDateInputs() {
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        // 设置默认值为今天
        if (!input.value) {
            const today = new Date().toISOString().split('T')[0];
            input.value = today;
        }
    });
}

// 初始化所有表单优化
window.addEventListener('load', function() {
    optimizeNumberInputs();
    optimizeDateInputs();
});