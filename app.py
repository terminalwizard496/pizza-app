from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import mysql.connector
import random
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "pizza_secret_key_123"

# ---- MySQL Connection ----
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "pizza_db")
        )
    except Exception as e:
        print("Database connection failed:", e)
        return None


# ---- ROUTES ----

@app.route('/')
def root():
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.json
    name = data.get('name')
    phone = data.get('phone')
    
    if not phone or not phone.isdigit() or len(phone) != 10:
        return jsonify({"success": False, "message": "❌ Invalid number!"})

    db = get_db_connection()
    if db:
        try:
            cursor = db.cursor()
            query = "INSERT INTO users (name, phone) VALUES (%s, %s) ON DUPLICATE KEY UPDATE name=%s"
            cursor.execute(query, (name, phone, name))
            db.commit()
            cursor.close()
            db.close()
            print(f"✅ User {name} saved to database.")
        except Exception as e:
            print(f"⚠️ Database Error: {e}")

    session.pop('generated_otp', None)
    otp = str(random.randint(1000, 9999))
    
    session['generated_otp'] = otp
    session['user_name'] = name
    session['phone'] = phone
    session.modified = True 
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open("otp_log.txt", "w") as f: 
            f.write(f"--- LATEST OTP REQUEST ---\nTIME: {now}\nNAME: {name}\nPHONE: {phone}\nCODE: {otp}\n")
    except Exception as e:
        print(f"File Error: {e}")

    return jsonify({"success": True, "message": "✅ OTP sent!"})

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.json
    if data.get('otp') == session.get('generated_otp'):
        session['logged_in'] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid OTP"})

@app.route('/menu')
def menu():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    cart_count = len(session.get('cart', []))
    return render_template('index.html', user_name=session.get('user_name'), cart_count=cart_count)

@app.route('/customize')
def customize():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    name = request.args.get('name')
    price = request.args.get('price')
    cart_count = len(session.get('cart', []))
    return render_template('customize.html', name=name, price=price, user_name=session.get('user_name'), cart_count=cart_count)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'cart' not in session:
        session['cart'] = []
    
    # Receive the full item object (name, price, toppings)
    item = request.json 
    
    # Update the session cart
    cart_list = list(session['cart']) 
    cart_list.append(item)
    
    session['cart'] = cart_list
    session.modified = True 
    return jsonify({"success": True, "count": len(session['cart'])})

@app.route('/cart_page')
def cart_page():
    if not session.get('logged_in'):
        return redirect(url_for('login_page'))
    
    # Fetch cart items from session
    cart_items = session.get('cart', [])
    
    # Calculate costs. item.get('price') handles the customized price sent from customize.html
    subtotal = sum(float(item.get('price', 0)) for item in cart_items)
    
    discount = 0
    if subtotal >= 3000:
        discount = subtotal * 0.15
    elif subtotal >= 2000:
        discount = subtotal * 0.10
        
    gst = round((subtotal - discount) * 0.05, 2)
    total = round((subtotal - discount) + gst, 2)
    
    # Fetch saved address from DB
    saved_address = ""
    db = get_db_connection()
    if db:
        cursor = db.cursor()
        cursor.execute("SELECT address FROM users WHERE phone = %s", (session.get('phone'),))
        result = cursor.fetchone()
        if result:
            saved_address = result[0]
        db.close()

    return render_template('cart.html', 
                           cart=cart_items, 
                           subtotal=subtotal, 
                           discount=round(discount, 2), 
                           gst=gst, 
                           total=total, 
                           saved_address=saved_address)

@app.route('/remove_from_cart/<int:index>')
def remove_from_cart(index):
    cart = session.get('cart', [])
    if 0 <= index < len(cart):
        cart.pop(index)
        session['cart'] = cart
        session.modified = True
    return redirect(url_for('cart_page'))

@app.route('/save_address', methods=['POST'])
def save_address():
    if not session.get('logged_in'):
        return jsonify({"success": False, "message": "Login required"})
    data = request.json
    address = data.get('address')
    phone = session.get('phone')
    db = get_db_connection()
    if db:
        try:
            cursor = db.cursor()
            query = "UPDATE users SET address = %s WHERE phone = %s"
            cursor.execute(query, (address, phone))
            db.commit()
            cursor.close()
            db.close()
            return jsonify({"success": True, "message": "Address updated!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    return jsonify({"success": False, "message": "DB Error"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

if __name__ == '__main__':
    print("--- 🍕 CIAO PIZZERIA IS LIVE ---")
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0",port=port)
    # app.run(debug=True)
