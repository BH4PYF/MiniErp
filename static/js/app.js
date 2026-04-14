// ========== 侧边栏切换 ==========
document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
        });
    }
});

// ========== CSRF Token 获取 ==========
function getCookie(name) {
    let v = null;
    if (document.cookie && document.cookie !== '') {
        document.cookie.split(';').forEach(function(c) {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                v = decodeURIComponent(c.substring(name.length + 1));
            }
        });
    }
    return v;
}
const csrftoken = getCookie('csrftoken');

// ========== 通用删除确认（模态框） ==========
var _deleteUrl = '';
var _deleteModal = null;

function confirmDelete(url, name) {
    _deleteUrl = url;
    var nameEl = document.getElementById('deleteItemName');
    if (nameEl) nameEl.textContent = name;

    if (!_deleteModal) {
        var el = document.getElementById('deleteConfirmModal');
        if (el) _deleteModal = new bootstrap.Modal(el);
    }
    if (_deleteModal) {
        _deleteModal.show();
    } else {
        // 回退：模态框不存在时用 confirm
        if (!confirm('确定要删除 "' + name + '" 吗？此操作不可恢复。')) return;
        _doDelete(url);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    var btn = document.getElementById('deleteConfirmBtn');
    if (btn) {
        btn.addEventListener('click', function() {
            if (_deleteModal) _deleteModal.hide();
            _doDelete(_deleteUrl);
        });
    }
});

function _doDelete(url) {
    fetch(url, {
        method: 'POST',
        headers: {'X-CSRFToken': csrftoken, 'Content-Type': 'application/json', 'Referer': window.location.href},
    }).then(function(resp) {
        return resp.json();
    }).then(function(data) {
        if (data.success) {
            showMsg('删除成功', 'success');
            // 等待用户关闭消息弹窗后再刷新页面
            const msgModalEl = document.getElementById('msgModal');
            if (msgModalEl) {
                msgModalEl.addEventListener('hidden.bs.modal', function onHidden() {
                    msgModalEl.removeEventListener('hidden.bs.modal', onHidden);
                    location.reload();
                });
            } else {
                // 如果消息模态框不存在，1秒后刷新页面
                setTimeout(() => location.reload(), 1000);
            }
        } else {
            showMsg(data.error || '删除失败');
        }
    }).catch(function() {
        showMsg('请求失败');
    });
}

// ========== 加载详情到模态框 ==========
function loadDetail(url, callback) {
    fetch(url).then(function(resp) {
        return resp.json();
    }).then(function(data) {
        callback(data);
    }).catch(function() {
        showMsg('加载失败');
    });
}

// ========== 审批操作 ==========
function approveAction(url, action) {
    var label = action === 'approve' ? '审批通过' : '取消';
    showConfirm('确定要' + label + '此采购计划吗？', function() {
        var formData = new FormData();
        formData.append('action', action);
        fetch(url, {
            method: 'POST',
            headers: {'X-CSRFToken': csrftoken},
            body: formData,
        }).then(function(resp) {
            return resp.json();
        }).then(function(data) {
            if (data.success) {
                location.reload();
            } else {
                showMsg(data.error || '操作失败');
            }
        });
    });
}

// ========== 格式化货币 ==========
function formatCurrency(n) {
    return parseFloat(n).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

// ========== 页面消息提示（顶部横幅，用于成功提示） ==========
function showAlert(message, type) {
    type = type || 'info';
    var container = document.querySelector('.main-content .px-3.pt-3');
    if (!container) {
        container = document.createElement('div');
        container.className = 'px-3 pt-3';
        var mainContent = document.querySelector('.main-content .p-3');
        if (mainContent) {
            mainContent.parentNode.insertBefore(container, mainContent);
        } else {
            document.body.prepend(container);
        }
    }
    var alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-' + type + ' alert-dismissible fade show';
    alertDiv.setAttribute('role', 'alert');
    alertDiv.textContent = message;
    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close';
    closeBtn.setAttribute('data-bs-dismiss', 'alert');
    alertDiv.appendChild(closeBtn);
    container.appendChild(alertDiv);
    setTimeout(function() {
        if (alertDiv.parentNode) alertDiv.remove();
    }, 5000);
}

// ========== 弹窗消息提示（模态框） ==========
function showMsg(message, type) {
    type = type || 'error';
    var modalEl = document.getElementById('msgModal');
    if (!modalEl) {
        // 如果模态框不存在（如登录页），回退到 alert
        alert(message);
        return;
    }
    var header = document.getElementById('msgModalHeader');
    var title = document.getElementById('msgModalTitle');
    var body = document.getElementById('msgModalBody');

    if (type === 'error' || type === 'danger') {
        header.className = 'modal-header py-2 bg-danger text-white';
        title.innerHTML = '<i class="bi bi-exclamation-circle"></i> 错误提示';
    } else if (type === 'warning') {
        header.className = 'modal-header py-2 bg-warning text-dark';
        title.innerHTML = '<i class="bi bi-exclamation-triangle"></i> 警告';
    } else if (type === 'success') {
        header.className = 'modal-header py-2 bg-success text-white';
        title.innerHTML = '<i class="bi bi-check-circle"></i> 成功';
    } else {
        header.className = 'modal-header py-2 bg-primary text-white';
        title.innerHTML = '<i class="bi bi-info-circle"></i> 提示';
    }
    body.textContent = message;
    var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
}

// ========== 通用确认模态框 ==========
var _confirmCallback = null;
var _confirmModal = null;

function showConfirm(message, callback) {
    _confirmCallback = callback;
    var modalEl = document.getElementById('confirmModal');
    if (!modalEl) {
        // 如果模态框不存在，回退到 confirm
        if (confirm(message)) {
            if (callback) callback();
        }
        return;
    }
    var body = document.getElementById('confirmModalBody');
    body.textContent = message;
    
    if (!_confirmModal) {
        _confirmModal = bootstrap.Modal.getOrCreateInstance(modalEl);
        // 绑定确认按钮事件
        var confirmBtn = document.getElementById('confirmModalBtn');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', function() {
                if (_confirmModal) _confirmModal.hide();
                if (_confirmCallback) _confirmCallback();
                _confirmCallback = null;
            });
        }
    }
    _confirmModal.show();
}

// ========== 通用 AJAX 表单提交 ==========
function ajaxSubmitForm(form, options) {
    options = options || {};
    var formData = new FormData(form);
    var submitBtn = form.querySelector('button[type="submit"]');
    var originalText = submitBtn ? submitBtn.innerHTML : '';
    
    // 显示加载状态
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 处理中...';
    }
    
    fetch(form.action, {
        method: 'POST',
        headers: {'X-CSRFToken': csrftoken, 'X-Requested-With': 'XMLHttpRequest'},
        body: formData,
    }).then(function(resp) {
        return resp.json();
    }).then(function(data) {
        if (data.success) {
            if (options.onSuccess) {
                options.onSuccess(data);
            } else {
                showMsg(data.message || '操作成功', 'success');
                // 保存项目字段的值
                var projectField = form.querySelector('[name="project_id"]');
                var projectValue = projectField ? projectField.value : '';
                
                // 重置表单
                form.reset();
                
                // 恢复项目字段的值
                if (projectField && projectValue) {
                    projectField.value = projectValue;
                }
                
                // 如果有模态框，关闭它
                var modalEl = form.closest('.modal');
                if (modalEl) {
                    var modal = bootstrap.Modal.getInstance(modalEl);
                    if (modal) modal.hide();
                }
                // 用户关闭消息弹窗后再刷新页面
                var msgModalEl = document.getElementById('msgModal');
                if (msgModalEl) {
                    msgModalEl.addEventListener('hidden.bs.modal', function onHidden() {
                        msgModalEl.removeEventListener('hidden.bs.modal', onHidden);
                        location.reload();
                    });
                } else {
                    setTimeout(function() { location.reload(); }, 800);
                }
            }
        } else {
            showMsg(data.error || '操作失败');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        }
    }).catch(function(err) {
        console.error('AJAX Error:', err);
        showMsg('请求失败，请重试');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    });
}

// 自动绑定所有 data-ajax 表单
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('form[data-ajax]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 检查是否指定了成功回调函数
            var successCallbackName = form.getAttribute('data-success-callback');
            var options = {};
            
            if (successCallbackName && typeof window[successCallbackName] === 'function') {
                options.onSuccess = window[successCallbackName];
            }
            
            ajaxSubmitForm(this, options);
        });
    });
});

// ========== 表格拖拽排序功能 ==========
function initTableDragSort(tableSelector) {
    const tables = document.querySelectorAll(tableSelector);
    tables.forEach(table => {
        const tbody = table.querySelector('tbody');
        if (!tbody) return;
        
        const rows = Array.from(tbody.querySelectorAll('tr'));
        rows.forEach(row => {
            row.draggable = true;
            row.style.cursor = 'move';
            
            row.addEventListener('dragstart', function(e) {
                this.classList.add('dragging');
                e.dataTransfer.setData('text/plain', this.rowIndex);
            });
            
            row.addEventListener('dragend', function() {
                this.classList.remove('dragging');
            });
        });
        
        tbody.addEventListener('dragover', function(e) {
            e.preventDefault();
            const draggingRow = document.querySelector('.dragging');
            const afterElement = getDragAfterElement(tbody, e.clientY);
            if (afterElement == null) {
                tbody.appendChild(draggingRow);
            } else {
                tbody.insertBefore(draggingRow, afterElement);
            }
        });
    });
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('tr:not(.dragging)')];
    
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// ========== 键盘快捷键支持 ==========
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + F: 聚焦搜索框
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();
        const searchInput = document.querySelector('input[name="q"], input[name="search"]');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }
    
    // Esc: 关闭模态框
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
            const modalInstance = bootstrap.Modal.getInstance(modal);
            if (modalInstance) {
                modalInstance.hide();
            }
        });
    }
    
    // Ctrl/Cmd + Enter: 提交当前表单
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        const focusedElement = document.activeElement;
        if (focusedElement && (focusedElement.form || focusedElement.closest('form'))) {
            e.preventDefault();
            const form = focusedElement.form || focusedElement.closest('form');
            const submitEvent = new Event('submit', { bubbles: true });
            form.dispatchEvent(submitEvent);
        }
    }
});

// ========== 表单自动保存功能 ==========
function initAutoSave(formSelector, interval = 30000) {
    const forms = document.querySelectorAll(formSelector);
    forms.forEach(form => {
        let autoSaveTimer;
        
        form.addEventListener('input', function() {
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(() => {
                autoSaveForm(form);
            }, interval);
        });
    });
}

function autoSaveForm(form) {
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    
    fetch(form.action, {
        method: 'POST',
        headers: {'X-CSRFToken': csrftoken, 'X-Requested-With': 'XMLHttpRequest'},
        body: formData,
    }).then(resp => resp.json())
      .then(data => {
          if (data.success) {
              showMsg('自动保存成功', 'success');
          }
      }).catch(err => {
          console.error('自动保存失败:', err);
      });
}
