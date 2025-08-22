from flask import Flask, request, jsonify
import re
from db import (get_or_create_user, get_or_create_group, add_group_member, 
                sync_group_members, set_group_split_count, get_group_members, 
                update_user_display_name)
from bot_commands import (handle_pay, handle_edit, handle_delete, handle_balance, 
                         handle_history, handle_members, handle_split, handle_alias,
                         handle_unalias, handle_aliases, HELP_TEXT)
import requests
from config import BOT_MENTION, LINE_CHANNEL_ACCESS_TOKEN

app = Flask(__name__)

def reply_line(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }
    r = requests.post(url, json=payload, headers=headers)
    return r.status_code, r.text

def get_line_profile(user_id):
    """ไม่ใช้ LINE Profile API - ให้ user ตั้งชื่อเอง"""
    # Skip LINE API completely - ประหยัดเวลาและไม่ error
    return "NewUser"  # ชื่อชั่วคราว ให้ user เปลี่ยนเอง

def get_group_members_from_line(group_id):
    """ดึงสมาชิกทั้งหมดในกลุ่มจาก LINE API"""
    url = f"https://api.line.me/v2/bot/group/{group_id}/members/ids"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            member_ids = data.get('memberIds', [])
            
            # ดึงโปรไฟล์แต่ละคน
            members = []
            for member_id in member_ids:
                # ข้ามบอท (ใส่ LINE Bot User ID ของคุณที่นี่)
                if member_id.startswith('U'):  # ปกติ user id จะขึ้นต้นด้วย U
                    display_name = get_line_profile(member_id)
                    if display_name != 'ไม่ทราบชื่อ':
                        members.append({
                            'line_user_id': member_id,
                            'display_name': display_name
                        })
            return members
    except Exception as e:
        print(f"Error getting group members: {e}")
    return []

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    event = data['events'][0]

    # Handle join event - เมื่อบอทถูกเพิ่มเข้ากลุ่ม
    if event['type'] == 'join' and event['source']['type'] == 'group':
        line_group_id = event['source']['groupId']
        reply_token = event['replyToken']
        
        # สร้างกลุ่มใหม่
        group_id = get_or_create_group(line_group_id, "Default")
        
        welcome_text = """🎉 Hello! I'm Billy Bot - your expense tracker!
สวัสดี! ผมคือ Billy Bot - ตัวช่วยจดบันทึกค่าใช้จ่าย!

📝 To get started, each member should:
เริ่มใช้งาน สมาชิกแต่ละคนทำตาม:

1. Send: @billybot register
   ส่ง: @billybot ลงทะเบียน  
2. Set your name: @billybot setname <your_name>
   ตั้งชื่อ: @billybot ตั้งชื่อ <ชื่อของคุณ>

Then you can start tracking expenses together!
แล้วเริ่มจดบันทึกค่าใช้จ่ายร่วมกันได้เลย!

💡 You can use Thai or English commands!
ใช้คำสั่งไทยหรืออังกฤษก็ได้!

Type '@billybot help' for all commands
พิมพ์ '@billybot ช่วยเหลือ' เพื่อดูคำสั่งทั้งหมด"""
        
        reply_line(reply_token, welcome_text)
        return jsonify({'status': 'ok'})

    # Handle member join event - เมื่อมีคนเข้ากลุ่มใหม่  
    if event['type'] == 'memberJoined' and event['source']['type'] == 'group':
        line_group_id = event['source']['groupId']
        reply_token = event['replyToken']
        
        welcome_text = """👋 Welcome to the group! 
ยินดีต้อนรับเข้ากลุ่ม!

Please send '@billybot register' to join our expense tracking.
กรุณาส่ง '@billybot ลงทะเบียน' เพื่อเข้าร่วมระบบจดบันทึกค่าใช้จ่าย

💡 You can use Thai or English commands!
ใช้คำสั่งไทยหรืออังกฤษก็ได้!"""
        
        reply_line(reply_token, welcome_text)
        return jsonify({'status': 'ok'})

    # Handle text messages
    if event['type'] != 'message' or event['message']['type'] != 'text':
        return jsonify({'status': 'ignored'})

    msg = event['message']['text'].strip()
    line_user_id = event['source']['userId']
    reply_token = event['replyToken']
    
    # ดึงชื่อจริงจาก LINE API
    display_name = get_line_profile(line_user_id)

    if not msg.lower().startswith(BOT_MENTION.lower()):
        return jsonify({'status':'ignored'})

    command_text = msg[len(BOT_MENTION):].strip()
    
    # ถ้าไม่มีคำสั่ง (เฉยๆ @billybot) ให้แสดง help
    if not command_text:
        reply_line(reply_token, HELP_TEXT)
        return jsonify({'status': 'ok'})

    # สร้างหรือดึง group และ user
    group_id = get_or_create_group(
        line_group_id=event['source'].get('groupId', f'private_{line_user_id}'),
        group_name="Default"
    )
    user_id = get_or_create_user(line_user_id, display_name)

    # แยกคำสั่ง
    cmd = command_text.split()[0].lower()

    try:
        # Handle register command - รองรับทั้งสองภาษา
        if cmd in ['register', 'ลงทะเบียน']:
            # เพิ่มผู้ใช้เป็นสมาชิกกลุ่ม
            add_group_member(group_id, user_id)
            
            # นับจำนวนสมาชิกปัจจุบัน
            members = get_group_members(group_id)
            member_count = len(members)
            
            # อัพเดท split count ตามจำนวนสมาชิก
            set_group_split_count(group_id, member_count)
            
            reply_text = f"✅ Registered successfully! Please set your name:\n"
            reply_text += f"@billybot setname <your_name>\n\n"
            reply_text += f"Group now has {member_count} members.\n\n"
            reply_text += f"🇹🇭 ลงทะเบียนสำเร็จ! กรุณาตั้งชื่อ:\n"
            reply_text += f"@billybot ตั้งชื่อ <ชื่อของคุณ>\n\n"
            reply_text += f"กลุ่มมีสมาชิก {member_count} คน"
            
        
        elif cmd in ['n', 'name', 'setname', 'ตั้งชื่อ']:
            from db import get_user_name_by_id
            current_name = get_user_name_by_id(user_id)
            
            reply_text = f"🔍 Debug Info:\n"
            reply_text += f"LINE User ID: {line_user_id}\n"
            reply_text += f"Database User ID: {user_id}\n"
            reply_text += f"Current Display Name: {current_name}\n"
            reply_text += f"Temporary Name: {display_name}"
            new_name = ' '.join(command_text.split()[1:])
            print(f"Updating user {user_id} (LINE: {line_user_id}) to name: {new_name}")

            success = update_user_display_name(user_id, new_name)
            
            if success:
                from db import get_user_name_by_id
                current_name = get_user_name_by_id(user_id)
                print(f"Current name in DB: {current_name}")
                
                reply_text = f"✅ Name updated to: {new_name} / อัพเดทชื่อเป็น: {new_name} แล้ว"
            else:
                reply_text = f"❌ Failed to update name / ไม่สามารถอัพเดทชื่อได้"
        
        else:
            add_group_member(group_id, user_id)
            
            # Dispatch other commands - รองรับทั้งสองภาษา
            if re.match(r'(@?\w+)?\s*(pay|return|จ่าย|คืน)', command_text, re.IGNORECASE):
                reply_text = handle_pay(command_text, user_id, group_id, display_name)
            
            elif cmd in ['m', 'member', 'members', 'สมาชิก']:
                reply_text = handle_members(group_id)
            
            elif cmd in ['s', 'split', 'แบ่ง']:
                reply_text = handle_split(command_text, group_id)
            
            elif cmd in ['a', 'alias', 'นามแฝง'] and len(command_text.split()) > 3:
                reply_text = handle_alias(command_text, group_id)
            
            elif cmd in ['c', 'una', 'cancel', 'unalias', 'ยกเลิก']:
                reply_text = handle_unalias(command_text, group_id)
            
            elif cmd in ['al', 'aliases', 'รายการนามแฝง']:
                reply_text = handle_aliases(group_id)
            
            elif cmd in ['e', 'edit', 'แก้ไข']:
                reply_text = handle_edit(command_text, group_id)
            
            elif cmd in ['d', 'delete', 'ลบ']:
                reply_text = handle_delete(command_text, group_id)
            
            elif cmd in ['b', 'balance', 'ยอด']:
                reply_text = handle_balance(group_id)
            
            elif cmd in ['h', 'history', 'บันทึก']:
                reply_text = handle_history(group_id)
            
            elif cmd in ['help', 'ช่วยเหลือ']:
                reply_text = HELP_TEXT
            
            else:
                reply_text = HELP_TEXT

    except Exception as e:
        reply_text = f"Error occurred / เกิดข้อผิดพลาด: {str(e)}"

    reply_line(reply_token, reply_text)
    return jsonify({'status':'ok'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)