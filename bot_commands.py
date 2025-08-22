import re
from db import (add_expense, edit_expense, delete_expense, get_balance_multi_user, 
               get_history, get_or_create_user, get_user_name_by_id, get_user_by_display_name,
               add_group_member, get_group_members, set_group_split_count, 
               get_group_split_count, get_expense_by_order, create_user_alias,
               remove_user_alias, get_user_aliases, get_main_user_id, get_effective_user_name)

HELP_TEXT = """🤖 Billy Bot - Expense Tracker / ตัวช่วยจดบันทึกค่าใช้จ่าย

🚀 Getting Started / เริ่มต้นใช้งาน:
@billybot register / ลงทะเบียน - Register to system / ลงทะเบียนเข้าระบบ
@billybot setname <n> / ตั้งชื่อ <ชื่อ> - Set your display name / ตั้งชื่อแสดงผล

💰 Payments / การจ่ายเงิน:
@billybot pay <amount> [detail] / จ่าย <จำนวน> [รายละเอียด] - Split payment / จ่ายเงินแบ่งกัน
@billybot @<n> pay <amount> [detail] / @<ชื่อ> จ่าย <จำนวน> [รายละเอียด] - Someone else pays / คนอื่นจ่าย
@billybot return <amount> [detail] / คืน <จำนวน> [รายละเอียด] - Return money / คืนเงิน

👥 Group Management / การจัดการกลุ่ม:
@billybot members / สมาชิก - Show all members / แสดงสมาชิกทั้งหมด
@billybot split <count> / แบ่ง <จำนวน> - Set split count / ตั้งจำนวนคนแบ่งกัน

🔗 Account Linking (Aliases) / การรวมบัญชี:
Use aliases when one person has multiple LINE accounts or names:
ใช้เมื่อคนหนึ่งมีหลายบัญชี LINE หรือหลายชื่อ:

@billybot alias @mainuser @aliasuser <display_name>
Example: @billybot alias @Get @GetWork GetOffice
This makes @GetWork transactions show as "GetOffice" under @Get's account
จะทำให้รายการของ @GetWork แสดงเป็น "GetOffice" ภายใต้บัญชีของ @Get

@billybot unalias @user / ยกเลิก @ผู้ใช้ - Remove alias / ยกเลิกการรวมบัญชี
@billybot aliases / รายการนามแฝง - Show all aliases / แสดงการรวมบัญชีทั้งหมด

📊 Reports / ดูข้อมูล:
@billybot balance / ยอด - Show balance / ดูยอดคงเหลือ
@billybot history / บันทึก - Show payment history / ดูประวัติการจ่าย

✏️ Edit/Delete / แก้ไข/ลบ:
@billybot edit <order> <amount> [detail] / แก้ไข <ลำดับ> <จำนวน> [รายละเอียด] - Edit transaction / แก้ไขรายการ
@billybot delete <order> / ลบ <ลำดับ> - Delete transaction / ลบรายการ

ℹ️ Help / ช่วยเหลือ:
@billybot help / ช่วยเหลือ - Show this help / แสดงความช่วยเหลือ
@billybot (without command) - Also shows help / ไม่ใส่คำสั่งก็แสดงความช่วยเหลือ

💡 Tip: You can use Thai or English commands! / เคล็ดลับ: ใช้คำสั่งไทยหรืออังกฤษก็ได้!
"""

def handle_pay(command_text, user_id, group_id, line_display_name):
    # เพิ่ม user เป็นสมาชิกกลุ่ม
    add_group_member(group_id, user_id)
    
    # รูปแบบ: [@ ชื่อ] (pay|return|จ่าย|คืน) <amount> [detail]
    match = re.match(r'(@(\w+))?\s*(pay|return|จ่าย|คืน)\s+(\d+\.?\d*)(.*)?', command_text, re.IGNORECASE)
    if not match:
        return "Format: pay <amount> [detail] or @name pay <amount> / รูปแบบ: pay <จำนวน> [รายละเอียด] หรือ @ชื่อ pay <จำนวน>"

    mention, target_name, action, amount_str, detail = match.groups()
    amount = float(amount_str)
    detail = detail.strip() if detail else ''

    # กรณีระบุชื่อคนจ่าย
    if mention:
        payer_id = get_user_by_display_name(group_id, target_name)
        if not payer_id:
            return f"Member {target_name} not found in group / ไม่พบสมาชิกชื่อ {target_name} ในกลุ่ม"
        payer_name = target_name
        recipient_name = "group/กลุ่ม"
        recipient_id = user_id  # ใช้คนที่สั่งเป็น recipient แทน
    else:
        # คนที่สั่งจ่ายเอง
        payer_id = user_id
        payer_name = line_display_name
        recipient_name = "group/กลุ่ม" 
        recipient_id = user_id  # placeholder

    # สลับถ้าเป็น return/คืน
    if action.lower() in ['return', 'คืน']:
        payer_id, recipient_id = recipient_id, payer_id
        payer_name, recipient_name = recipient_name, payer_name

    expense_id = add_expense(group_id, payer_id, recipient_id, amount, 'pay', detail)

    reply = f'✅ Recorded: {payer_name} paid {amount} baht / บันทึกแล้ว: {payer_name} จ่าย {amount} บาท'
    if detail:
        reply += f' ({detail})'
    return reply

def handle_members(group_id):
    """แสดงสมาชิกทั้งหมดในกลุ่ม พร้อม aliases"""
    members = get_group_members(group_id)
    aliases = get_user_aliases(group_id)
    split_count = get_group_split_count(group_id)
    
    if not members:
        return "No members in group yet / ยังไม่มีสมาชิกในกลุ่ม"
    
    # สร้าง dict ของ aliases
    alias_dict = {}
    for alias in aliases:
        main_id = alias['main_user_id']
        if main_id not in alias_dict:
            alias_dict[main_id] = []
        alias_dict[main_id].append({
            'name': alias['alias_name'],
            'user_id': alias['alias_user_id']
        })
    
    member_list = []
    shown_main_users = set()
    
    for i, member in enumerate(members, 1):
        member_id = member['id']
        main_id = get_main_user_id(group_id, member_id)
        
        # ถ้าเป็น main user หรือยังไม่แสดง main user นี้
        if main_id == member_id:
            if main_id not in shown_main_users:
                line = f"{i}. {member['display_name']}"
                if main_id in alias_dict:
                    alias_names = [a['name'] for a in alias_dict[main_id]]
                    line += f" (aliases: {', '.join(alias_names)})"
                member_list.append(line)
                shown_main_users.add(main_id)
        else:
            # เป็น alias - ถ้ายังไม่แสดง main user
            if main_id not in shown_main_users:
                main_name = get_user_name_by_id(main_id)
                line = f"{i}. {main_name}"
                if main_id in alias_dict:
                    alias_names = [a['name'] for a in alias_dict[main_id]]
                    line += f" (aliases: {', '.join(alias_names)})"
                member_list.append(line)
                shown_main_users.add(main_id)
    
    result = f"👥 Group members (split between {split_count} people) / สมาชิกในกลุ่ม (แบ่งกัน {split_count} คน):\n"
    result += "\n".join(member_list)
    return result

def handle_split(command_text, group_id):
    """ตั้งค่าจำนวนคนแบ่งกัน - รองรับสองภาษา"""
    match = re.match(r'(s|split|แบ่ง)\s+(\d+)', command_text, re.IGNORECASE)
    if not match:
        return "Format: split <number> / รูปแบบ: split <จำนวนคน>"
    
    count = int(match.group(2))
    if count < 1:
        return "Number must be greater than 0 / จำนวนคนต้องมากกว่า 0"
    
    set_group_split_count(group_id, count)
    return f"✅ Split count set to {count} people / ตั้งค่าแบ่งกัน {count} คนแล้ว"

def handle_alias(command_text, group_id):
    """สร้าง alias - รวมหลายบัญชีเป็นคนเดียวกัน - รองรับสองภาษา"""
    # รูปแบบ: alias @user1 @user2 name
    match = re.match(r'(a|alias|นามแฝง)\s+@(\w+)\s+@(\w+)\s+(.+)', command_text, re.IGNORECASE)
    if not match:
        return "Format: alias @mainuser @aliasuser <alias_name> / รูปแบบ: alias @คนหลัก @คนแฝง <ชื่อแฝง>"
    
    _, main_name, alias_name_user, alias_display_name = match.groups()
    alias_display_name = alias_display_name.strip()
    
    # หา user IDs
    main_user_id = get_user_by_display_name(group_id, main_name)
    alias_user_id = get_user_by_display_name(group_id, alias_name_user)
    
    if not main_user_id:
        return f"Main user '{main_name}' not found / ไม่พบผู้ใช้หลัก '{main_name}'"
    if not alias_user_id:
        return f"Alias user '{alias_name_user}' not found / ไม่พบผู้ใช้แฝง '{alias_name_user}'"
    if main_user_id == alias_user_id:
        return "Cannot alias user to themselves / ไม่สามารถตั้ง alias ให้ตัวเองได้"
    
    success, message = create_user_alias(group_id, main_user_id, alias_user_id, alias_display_name)
    
    if success:
        return f"✅ Alias created: {alias_name_user} → {main_name} (display as: {alias_display_name}) / สร้าง alias: {alias_name_user} → {main_name} (แสดงเป็น: {alias_display_name})"
    else:
        return f"❌ {message}"

def handle_unalias(command_text, group_id):
    """ยกเลิก alias - รองรับสองภาษา"""
    # รูปแบบ: unalias @user หรือ ยกเลิก @user
    match = re.match(r'(c|anscel|una|unalias|ยกเลิก)\s+@(\w+)', command_text, re.IGNORECASE)
    if not match:
        return "Format: unalias @username / รูปแบบ: unalias @ชื่อผู้ใช้"
    
    _, username = match.groups()
    
    # หา user ID
    user_id = get_user_by_display_name(group_id, username)
    if not user_id:
        return f"User '{username}' not found / ไม่พบผู้ใช้ '{username}'"
    
    if remove_user_alias(group_id, user_id):
        return f"✅ Alias removed for {username} / ยกเลิก alias สำหรับ {username} แล้ว"
    else:
        return f"❌ {username} has no alias to remove / {username} ไม่มี alias ให้ยกเลิก"

def handle_aliases(group_id):
    """แสดง aliases ทั้งหมด"""
    aliases = get_user_aliases(group_id)
    
    if not aliases:
        return "No aliases set / ยังไม่มีการตั้ง alias"
    
    lines = ["🔗 Aliases in this group / นามแฝงในกลุ่มนี้:"]
    
    for alias in aliases:
        main_name = get_user_name_by_id(alias['main_user_id'])
        alias_user_name = get_user_name_by_id(alias['alias_user_id'])
        lines.append(f"• {alias_user_name} → {main_name} (as: {alias['alias_name']})")
    
    return "\n".join(lines)

def handle_edit(command_text, group_id):
    """แก้ไขรายการโดยใช้เลขลำดับ - รองรับสองภาษา"""
    match = re.match(r'(e|edit|แก้ไข)\s+(\d+)\s+(\d+\.?\d*)(.*)?', command_text, re.IGNORECASE)
    if not match:
        return "Format: edit <order> <amount> [detail] / รูปแบบ: edit <เลขลำดับ> <จำนวนเงิน> [รายละเอียด]"
    
    _, order_str, amount_str, detail = match.groups()
    order_number = int(order_str)
    amount = float(amount_str)
    detail = detail.strip() if detail else None
    
    expense_id = get_expense_by_order(group_id, order_number)
    if not expense_id:
        return f"Item #{order_number} not found / ไม่พบรายการลำดับที่ {order_number}"
    
    edit_expense(expense_id, amount, detail)
    return f'✏️ Edited item #{order_number} / แก้ไขรายการลำดับที่ {order_number} เรียบร้อย'

def handle_delete(command_text, group_id):
    """ลบรายการโดยใช้เลขลำดับ - รองรับสองภาษา"""
    match = re.match(r'(d|delete|ลบ)\s+(\d+)', command_text, re.IGNORECASE)
    if not match:
        return "Format: delete <order> / รูปแบบ: delete <เลขลำดับ>"
    
    order_number = int(match.group(2))
    expense_id = get_expense_by_order(group_id, order_number)
    if not expense_id:
        return f"Item #{order_number} not found / ไม่พบรายการลำดับที่ {order_number}"
    
    delete_expense(expense_id)
    return f'🗑 Deleted item #{order_number} / ลบรายการลำดับที่ {order_number} เรียบร้อย'

def handle_balance(group_id):
    """แสดงยอดคงเหลือสำหรับหลายคน"""
    balances, total_expenses, should_pay_per_person = get_balance_multi_user(group_id)
    split_count = get_group_split_count(group_id)
    
    if not balances:
        return "No expenses yet / ยังไม่มีรายการจ่าย"
    
    result = f"💰 Balance (Total: {total_expenses:.2f} baht, {split_count} people) / ยอดคงเหลือ (รวม {total_expenses:.2f} บาท, แบ่งกัน {split_count} คน)\n"
    result += f"Each person should pay: {should_pay_per_person:.2f} baht / คนละ {should_pay_per_person:.2f} บาท\n\n"
    
    owes = []  # คนที่ต้องจ่าย
    gets = []  # คนที่ได้รับ
    
    for name, balance in balances.items():
        if balance > 0.01:  # จ่ายเกิน
            gets.append(f"✅ {name}: overpaid {balance:.2f} baht / จ่ายเกิน {balance:.2f} บาท")
        elif balance < -0.01:  # จ่ายน้อย
            owes.append(f"💸 {name}: owes {abs(balance):.2f} baht / ต้องจ่ายอีก {abs(balance):.2f} บาท")
        else:  # พอดี
            result += f"⚖️ {name}: paid exactly / จ่ายพอดี\n"
    
    if gets:
        result += "\n".join(gets) + "\n"
    if owes:
        result += "\n".join(owes)
    
    return result

def handle_history(group_id):
    """แสดงประวัติการจ่าย พร้อมเลขลำดับ"""
    rows = get_history(group_id)
    if not rows:
        return 'No expenses yet / ยังไม่มีรายการจ่าย'

    lines = ['📋 Payment history / ประวัติการจ่าย:']
    
    for i, r in enumerate(rows, 1):
        # ใช้ effective name (อาจเป็น alias name)
        payer_name = get_effective_user_name(group_id, r['user_id'])
        detail_text = f" ({r['detail']})" if r.get('detail') else ''
        
        timestamp = r.get('created_at', '')
        try:
            date_only = timestamp.split('T')[0]
            date_only = '/'.join(date_only.split('-'))
        except:
            date_only = timestamp

        lines.append(f"{i:2d}. {date_only} - {payer_name} paid / จ่าย {r['amount']:.2f} baht/บาท{detail_text}")

    # แสดงยอดรวมด้วย
    _, total_expenses, should_pay_per_person = get_balance_multi_user(group_id)
    split_count = get_group_split_count(group_id)
    lines.append(f"\n💰 Total: {total_expenses:.2f} baht ({split_count} people, {should_pay_per_person:.2f} each) / รวม {total_expenses:.2f} บาท (แบ่งกัน {split_count} คน, คนละ {should_pay_per_person:.2f} บาท)")
    
    return '\n'.join(lines)