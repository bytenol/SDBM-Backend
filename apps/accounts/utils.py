import datetime
from django.contrib.auth import get_user_model


User = get_user_model()


def generate_login_id(role_name):
    """
    Generates a unique login ID based on role prefix and current year.
    Examples: STU-2026-0001, STF-2026-0001, ADM-2026-0001
    """
    current_year = datetime.date.today().year
    prefix_map = {
        'STUDENT': 'STU',
        'STAFF': 'STF',
        'ADMIN': 'ADM',
        'SUPER_ADMIN': 'SUP'
    }

    prefix = prefix_map.get(role_name, 'USR')
    
    
    pattern = f"{prefix}-{current_year}-"
    last_user = User.objects.filter(login_id__startswith=pattern).order_by('login_id').last()
    
    if last_user and last_user.login_id:
        try:
            last_seq = int(last_user.login_id.split('-')[-1])
            new_seq = last_seq + 1
        except ValueError:
            new_seq = 1
    else:
        new_seq = 1
        
    return f"{prefix}-{current_year}-{new_seq:04d}"