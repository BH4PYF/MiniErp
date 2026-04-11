from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
import re


class CustomPasswordValidator:
    """自定义密码验证器，要求密码包含大小写字母、数字和特殊字符"""
    
    def __init__(self, min_length=12, require_uppercase=True, require_lowercase=True, require_digit=True, require_special=True):
        self.min_length = min_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digit = require_digit
        self.require_special = require_special
    
    def validate(self, password, user=None):
        """验证密码是否符合要求"""
        # 调用Django的默认密码验证器
        validate_password(password, user)
        
        # 检查密码长度
        if len(password) < self.min_length:
            raise ValidationError(
                f"密码长度必须至少为{self.min_length}个字符",
                code='password_too_short',
            )
        
        # 检查是否包含大写字母
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            raise ValidationError(
                "密码必须包含至少一个大写字母",
                code='password_no_uppercase',
            )
        
        # 检查是否包含小写字母
        if self.require_lowercase and not re.search(r'[a-z]', password):
            raise ValidationError(
                "密码必须包含至少一个小写字母",
                code='password_no_lowercase',
            )
        
        # 检查是否包含数字
        if self.require_digit and not re.search(r'[0-9]', password):
            raise ValidationError(
                "密码必须包含至少一个数字",
                code='password_no_digit',
            )
        
        # 检查是否包含特殊字符
        if self.require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                "密码必须包含至少一个特殊字符",
                code='password_no_special',
            )
    
    def get_help_text(self):
        """返回密码验证的帮助文本"""
        help_text = f"密码长度必须至少为{self.min_length}个字符"
        if self.require_uppercase:
            help_text += "，包含至少一个大写字母"
        if self.require_lowercase:
            help_text += "，包含至少一个小写字母"
        if self.require_digit:
            help_text += "，包含至少一个数字"
        if self.require_special:
            help_text += "，包含至少一个特殊字符"
        return help_text