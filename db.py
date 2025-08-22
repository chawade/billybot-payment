import uuid
from datetime import datetime
from config import supabase

def get_or_create_user(line_user_id, display_name):
    print(f"Getting or creating user: LINE ID = {line_user_id}, display_name = {display_name}")
    
    user = supabase.table('User').select('*').eq('line_user_id', line_user_id).execute().data
    print(f"Found existing user: {user}")
    
    if user: 
        user_id = user[0]['id']
        current_name = user[0]['display_name']
        print(f"User exists: ID = {user_id}, current name = {current_name}")
        
        # อัพเดท display_name ถ้าเปลี่ยน (แต่อาจไม่จำเป็นเพราะเราจะใช้ setname แทน)
        if current_name != display_name and display_name != "NewUser":
            print(f"Updating display name from {current_name} to {display_name}")
            supabase.table('User').update({'display_name': display_name}).eq('id', user_id).execute()
        
        return user_id
    
    # สร้างใหม่
    new_user_id = str(uuid.uuid4())
    print(f"Creating new user: ID = {new_user_id}")
    
    result = supabase.table('User').insert({
        'id': new_user_id,
        'line_user_id': line_user_id,
        'display_name': display_name,
        'created_at': datetime.now().isoformat()
    }).execute()
    
    print(f"Created user result: {result.data}")
    return new_user_id

def get_user_name_by_id(user_id):
    user = supabase.table('User').select('display_name').eq('id', user_id).execute().data
    if user:
        return user[0]['display_name']
    return 'ไม่ทราบชื่อ'

def update_user_display_name(user_id, new_display_name):
    """อัพเดทชื่อแสดงผลของผู้ใช้"""
    try:
        print(f"Attempting to update user {user_id} to name: {new_display_name}")
        
        # ตรวจสอบว่า user มีอยู่จริงก่อน
        existing_user = supabase.table('User').select('*').eq('id', user_id).execute()
        print(f"Existing user data: {existing_user.data}")
        
        if not existing_user.data:
            print(f"User {user_id} not found!")
            return False
        
        # ทำการอัพเดท
        result = supabase.table('User').update({'display_name': new_display_name}).eq('id', user_id).execute()
        print(f"Update result: {result}")
        print(f"Update data: {result.data}")
        
        # ตรวจสอบหลังอัพเดท
        updated_user = supabase.table('User').select('*').eq('id', user_id).execute()
        print(f"After update: {updated_user.data}")
        
        return len(result.data) > 0
    except Exception as e:
        print(f"Error updating user display name: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_user_by_display_name(group_id, display_name):
    """หา user จากชื่อใน group"""
    # หา users ทั้งหมดใน group
    members = get_group_members(group_id)
    for member in members:
        if member['display_name'].lower() == display_name.lower():
            return member['id']
    return None

def get_or_create_group(line_group_id, group_name="Default"):
    group = supabase.table('Groups').select('*').eq('line_group_id', line_group_id).execute().data
    if group:
        return group[0]['id']
    
    group_id = str(uuid.uuid4())
    supabase.table('Groups').insert({
        'id': group_id,
        'line_group_id': line_group_id,
        'name': group_name,
        'split_count': 2,  # default แบ่งกันสองคน
        'created_at': datetime.now().isoformat()
    }).execute()
    return group_id

def add_group_member(group_id, user_id):
    """เพิ่มสมาชิกใน group"""
    existing = supabase.table('GroupMembers').select('*').eq('group_id', group_id).eq('user_id', user_id).execute().data
    if not existing:
        supabase.table('GroupMembers').insert({
            'id': str(uuid.uuid4()),
            'group_id': group_id,
            'user_id': user_id,
            'created_at': datetime.now().isoformat()
        }).execute()

def sync_group_members(group_id, line_members):
    """ซิงค์สมาชิกทั้งหมดจาก LINE API เข้าฐานข้อมูล"""
    member_count = 0
    
    for member_data in line_members:
        line_user_id = member_data['line_user_id']
        display_name = member_data['display_name']
        
        # สร้างหรืออัพเดท user
        user_id = get_or_create_user(line_user_id, display_name)
        
        # เพิ่มเป็นสมาชิกกลุ่ม
        add_group_member(group_id, user_id)
        member_count += 1
    
    return member_count

def get_group_members(group_id):
    """ดึงสมาชิกทั้งหมดใน group"""
    result = supabase.table('GroupMembers').select('''
        user_id,
        User!inner(id, display_name, line_user_id)
    ''').eq('group_id', group_id).execute().data
    
    members = []
    for row in result:
        user = row['User']
        members.append({
            'id': user['id'],
            'display_name': user['display_name'],
            'line_user_id': user['line_user_id']
        })
    return members

def set_group_split_count(group_id, count):
    """ตั้งค่าจำนวนคนที่จะแบ่งกัน"""
    supabase.table('Groups').update({'split_count': count}).eq('id', group_id).execute()

def get_group_split_count(group_id):
    """ดึงจำนวนคนที่จะแบ่งกัน"""
    result = supabase.table('Groups').select('split_count').eq('id', group_id).execute().data
    return result[0]['split_count'] if result else 2

def create_user_alias(group_id, main_user_id, alias_user_id, alias_name):
    """สร้าง alias ให้ user - รวมหลายบัญชีเป็นคนเดียวกัน"""
    # ตรวจสอบว่า main_user_id และ alias_user_id อยู่ในกลุ่มเดียวกัน
    members = get_group_members(group_id)
    member_ids = [m['id'] for m in members]
    
    if main_user_id not in member_ids or alias_user_id not in member_ids:
        return False, "Both users must be members of the group"
    
    # ตรวจสอบว่ามี alias อยู่แล้วหรือไม่
    existing = supabase.table('UserAliases').select('*').eq('group_id', group_id).eq('alias_user_id', alias_user_id).execute().data
    if existing:
        return False, "This user already has an alias set"
    
    # สร้าง alias
    supabase.table('UserAliases').insert({
        'id': str(uuid.uuid4()),
        'group_id': group_id,
        'main_user_id': main_user_id,
        'alias_user_id': alias_user_id,
        'alias_name': alias_name,
        'created_at': datetime.now().isoformat()
    }).execute()
    
    return True, "Alias created successfully"

def remove_user_alias(group_id, alias_user_id):
    """ลบ alias"""
    result = supabase.table('UserAliases').delete().eq('group_id', group_id).eq('alias_user_id', alias_user_id).execute()
    return len(result.data) > 0

def get_user_aliases(group_id):
    """ดึง aliases ทั้งหมดในกลุ่ม"""
    return supabase.table('UserAliases').select('*').eq('group_id', group_id).execute().data

def get_main_user_id(group_id, user_id):
    """ดึง main_user_id ถ้า user_id เป็น alias, ถ้าไม่ใช่ก็คืน user_id เดิม"""
    alias = supabase.table('UserAliases').select('main_user_id').eq('group_id', group_id).eq('alias_user_id', user_id).execute().data
    if alias:
        return alias[0]['main_user_id']
    return user_id

def get_effective_user_name(group_id, user_id):
    """ดึงชื่อที่แสดง - ถ้าเป็น alias จะใช้ alias_name"""
    alias = supabase.table('UserAliases').select('alias_name').eq('group_id', group_id).eq('alias_user_id', user_id).execute().data
    if alias:
        return alias[0]['alias_name']
    return get_user_name_by_id(user_id)

def add_expense(group_id, user_id, recipient_id, amount, type_, detail=''):
    return supabase.table('Expenses').insert({
        'id': str(uuid.uuid4()),
        'group_id': group_id,
        'user_id': user_id,
        'recipient_id': recipient_id,
        'amount': amount,
        'type': type_,
        'detail': detail,
        'created_at': datetime.now().isoformat()
    }).execute().data[0]['id']

def edit_expense(expense_id, amount=None, detail=None):
    update = {}
    if amount is not None: 
        update['amount'] = amount
    if detail is not None: 
        update['detail'] = detail
    supabase.table('Expenses').update(update).eq('id', expense_id).execute()

def delete_expense(expense_id):
    supabase.table('Expenses').delete().eq('id', expense_id).execute()

def get_balance_multi_user(group_id):
    """คำนวณยอดสำหรับหลายคน โดยรวม aliases เข้าด้วยกัน"""
    members = get_group_members(group_id)
    aliases = get_user_aliases(group_id)
    split_count = get_group_split_count(group_id)
    
    # ดึงรายการจ่ายทั้งหมด
    expenses = supabase.table('Expenses').select('*').eq('group_id', group_id).execute().data
    
    # คำนวณยอดรวมที่จ่ายโดยแต่ละคน (รวม aliases)
    paid_by = {}
    
    # เตรียม paid_by สำหรับ main users เท่านั้น
    main_user_ids = set()
    for member in members:
        main_id = get_main_user_id(group_id, member['id'])
        main_user_ids.add(main_id)
        if main_id not in paid_by:
            paid_by[main_id] = 0
    
    total_expenses = 0
    for expense in expenses:
        # แปลง user_id เป็น main_user_id
        main_user_id = get_main_user_id(group_id, expense['user_id'])
        
        if expense['type'] == 'pay':
            paid_by[main_user_id] += expense['amount']
            total_expenses += expense['amount']
        elif expense['type'] == 'return':
            paid_by[main_user_id] -= expense['amount']
            total_expenses -= expense['amount']
    
    # คำนวณยอดที่แต่ละคนควรจ่าย
    should_pay_per_person = total_expenses / split_count
    
    # คำนวณยอดคงเหลือ โดยใช้ชื่อที่แสดง
    balances = {}
    for main_user_id in main_user_ids:
        balance = paid_by.get(main_user_id, 0) - should_pay_per_person
        # ใช้ชื่อจาก main user
        display_name = get_user_name_by_id(main_user_id)
        balances[display_name] = balance
    
    return balances, total_expenses, should_pay_per_person

def get_history(group_id, limit=20):
    return supabase.table('Expenses').select('*').eq('group_id', group_id).order('created_at', desc=True).limit(limit).execute().data

def get_expense_by_order(group_id, order_number):
    """ดึง expense จากเลขลำดับ"""
    expenses = get_history(group_id, limit=100)  # ดึงมาเยอะหน่อย
    if 1 <= order_number <= len(expenses):
        return expenses[order_number - 1]['id']
    return None