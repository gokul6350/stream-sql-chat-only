import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
from num2words import num2words
import os
import pdfkit  # Add this import at the top
import subprocess  # Add this import at the top

config = pdfkit.configuration(wkhtmltopdf="C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe")
# Initialize SQLite database
conn = sqlite3.connect('pharmacy_inventory.db', check_same_thread=False)
c = conn.cursor()

# Create table if not exists
c.execute('''CREATE TABLE IF NOT EXISTS inventory
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              medicine_name TEXT,
              quantity INTEGER,
              manufacturer TEXT,
              supplier TEXT,
              supplier_price REAL,
              batch_no TEXT,
              exp_mfg_date DATE,
              amount REAL,
              paid BOOLEAN)''')
conn.commit()

# Create table for invoices if not exists
c.execute('''CREATE TABLE IF NOT EXISTS invoices
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              invoice_no TEXT,
              customer_name TEXT,
              customer_phone TEXT,
              total_amount REAL,
              date DATE,
              paid BOOLEAN)''')
conn.commit()

# Create table for invoice items if not exists
c.execute('''CREATE TABLE IF NOT EXISTS invoice_items
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              invoice_id INTEGER,
              medicine_name TEXT,
              quantity INTEGER,
              rate REAL,
              total REAL,
              FOREIGN KEY (invoice_id) REFERENCES invoices (id))''')
conn.commit()

def ensure_history_folder():
    if not os.path.exists('history'):
        os.makedirs('history')

def save_invoice_pdf(invoice_no, html_content):
    try:
        ensure_history_folder()
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Get absolute path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_dir, 'history', f'invoice_{invoice_no}_{timestamp}.pdf')
        
        print(f"Attempting to save PDF at: {file_path}")  # Debug print
        
        # Convert HTML to PDF
        pdfkit.from_string(html_content, file_path, configuration=config)
        print(f"PDF saved successfully at: {file_path}")  # Debug print
        
        # Verify file exists
        if os.path.exists(file_path):
            print(f"File verified to exist at: {file_path}")  # Debug print
            return file_path
        else:
            print(f"File not found after creation at: {file_path}")  # Debug print
            return None
            
    except Exception as e:
        print(f"Error saving PDF: {str(e)}")  # Debug print
        return None

def inventory_management():
    st.title("Pharmacy Inventory Management")

    # Sidebar for adding new columns and editing existing entries
    with st.sidebar:
        st.header("Add New Column")
        new_column = st.text_input("New Column Name")
        column_type = st.selectbox("Column Type", ["TEXT", "INTEGER", "REAL", "DATE", "BOOLEAN"])
        if st.button("Add Column"):
            add_new_column(new_column, column_type)
        
        st.markdown("---")
        
        st.header("Edit Existing Entry")
        if st.button("Edit Product"):
            st.session_state.show_edit_popup = True

    # Main content
    st.header("View Inventory")
    display_inventory()

    st.markdown("---")

    st.header("Add/Edit Inventory")
    add_edit_inventory()

    # Edit popup
    if st.session_state.get('show_edit_popup', False):
        with st.expander("Edit Existing Product", expanded=True):
            edit_existing_product()

def invoice_generator():
    st.title("Invoice Generator")

    col1, col2 = st.columns([1, 2])  # Adjust the ratio to give more space to the preview

    with col1:
        invoice_no = st.text_input("Invoice No.", "INV-" + date.today().strftime("%Y%m%d-001"))
        customer_name = st.text_input("Customer Name")
        customer_phone = st.text_input("Customer Phone")

        st.subheader("Add Items")
        medicine_name = st.selectbox("Select Medicine", get_medicine_names())
        quantity = st.number_input("Quantity", min_value=1, value=1)
        
        if medicine_name:
            medicine_details = get_medicine_details(medicine_name)
            if medicine_details:
                st.write(f"Available Quantity: {medicine_details['quantity']}")
                st.write(f"Rate: ₹{medicine_details['amount']:.2f}")
                
                if st.button("Add to Invoice"):
                    add_item_to_invoice(medicine_name, quantity, medicine_details['amount'])

        st.subheader("Invoice Items")
        display_invoice_items()

        if st.button("Generate Invoice"):
            generate_invoice(invoice_no, customer_name, customer_phone)

    with col2:
        st.subheader("Invoice Preview")
        display_invoice_preview(invoice_no, customer_name, customer_phone)

def get_medicine_names():
    c.execute("SELECT DISTINCT medicine_name FROM inventory")
    return [row[0] for row in c.fetchall()]

def get_medicine_details(medicine_name):
    c.execute("SELECT quantity, amount, manufacturer, batch_no, exp_mfg_date FROM inventory WHERE medicine_name = ?", (medicine_name,))
    result = c.fetchone()
    if result:
        return {"quantity": result[0], "amount": result[1], "manufacturer": result[2], "batch_no": result[3], "exp_mfg_date": result[4]}
    return None

def add_item_to_invoice(medicine_name, quantity, rate):
    if 'invoice_items' not in st.session_state:
        st.session_state.invoice_items = []
    
    total = quantity * rate
    st.session_state.invoice_items.append({
        "medicine_name": medicine_name,
        "quantity": quantity,
        "rate": rate,
        "total": total
    })
    st.success(f"Added {medicine_name} to the invoice.")

def display_invoice_items():
    if 'invoice_items' in st.session_state and st.session_state.invoice_items:
        df = pd.DataFrame(st.session_state.invoice_items)
        st.dataframe(df)
        
        total_amount = df['total'].sum()
        st.write(f"Total Amount: ₹{total_amount:.2f}")
    else:
        st.write("No items added to the invoice yet.")

def generate_invoice(invoice_no, customer_name, customer_phone):
    if 'invoice_items' not in st.session_state or not st.session_state.invoice_items:
        st.error("Please add items to the invoice before generating.")
        return

    total_amount = sum(item['total'] for item in st.session_state.invoice_items)
    
    # Save invoice to database
    c.execute('''INSERT INTO invoices (invoice_no, customer_name, customer_phone, total_amount, date, paid)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (invoice_no, customer_name, customer_phone, total_amount, date.today(), False))
    invoice_id = c.lastrowid

    # Save invoice items to database
    for item in st.session_state.invoice_items:
        c.execute('''INSERT INTO invoice_items (invoice_id, medicine_name, quantity, rate, total)
                     VALUES (?, ?, ?, ?, ?)''',
                  (invoice_id, item['medicine_name'], item['quantity'], item['rate'], item['total']))

    conn.commit()

    st.success("Invoice generated successfully!")
    st.session_state.invoice_items = []  # Clear the invoice items

def display_invoice_preview(invoice_no, customer_name, customer_phone):
    if 'invoice_items' in st.session_state and st.session_state.invoice_items:
        items = []
        for item in st.session_state.invoice_items:
            medicine_details = get_medicine_details(item['medicine_name'])
            items.append({
                'medicine_name': item['medicine_name'],
                'quantity': item['quantity'],
                'manufacturer': medicine_details.get('manufacturer', ''),
                'batch_no': medicine_details.get('batch_no', ''),
                'exp_mfg_date': medicine_details.get('exp_mfg_date', ''),
                'rate': item['rate'],
                'total': item['total']
            })
        html = generate_invoice_html(invoice_no, customer_name, customer_phone, items)
        st.components.v1.html(html, height=800, scrolling=True)
        
        # Add print button
        if st.button("Print Invoice"):
            print("Print button clicked")  # Debug print
            # Save the invoice as PDF
            pdf_path = save_invoice_pdf(invoice_no, html)
            if pdf_path and os.path.exists(pdf_path):
                st.success(f"Invoice PDF saved to {pdf_path}")
                # Open PDF with system default PDF viewer
                try:
                    print(f"Attempting to open: {pdf_path}")  # Debug print
                    if os.name == 'nt':  # For Windows
                        os.startfile(os.path.abspath(pdf_path), 'print')
                    elif os.name == 'posix':  # For Linux/Mac
                        subprocess.run(['xdg-open', pdf_path])
                    print("Print command executed successfully")  # Debug print
                except Exception as e:
                    print(f"Error opening PDF: {str(e)}")  # Debug print
                    st.error(f"Could not open PDF automatically. File location: {pdf_path}")
                
                # Still provide download button as backup
                with open(pdf_path, "rb") as pdf_file:
                    PDFbyte = pdf_file.read()
                st.download_button(
                    label="Download Invoice PDF",
                    data=PDFbyte,
                    file_name=os.path.basename(pdf_path),
                    mime='application/pdf'
                )
            else:
                st.error("Failed to generate PDF. Please check the logs.")

def generate_invoice_html(invoice_no, customer_name, customer_phone, items):
    items_html = ""
    total_quantity = 0
    total_value = 0
    for item in items:
        items_html += f"""
        <tr>
            <td>{item['medicine_name']}</td>
            <td>{item['quantity']}</td>
            <td>{item['manufacturer']}</td>
            <td>{item['batch_no']}</td>
            <td>{item['exp_mfg_date']}</td>
            <td>{item['rate']:.2f}</td>
            <td>{item['total']:.2f}</td>
        </tr>
        """
        total_quantity += item['quantity']
        total_value += item['total']

    html = f"""
    <style>
        .invoice-box {{ width: 100%; margin: auto; padding: 30px; border: 1px solid #eee; box-shadow: 0 0 10px rgba(0, 0, 0, .15); font-size: 16px; line-height: 24px; font-family: 'Helvetica Neue', 'Helvetica', Helvetica, Arial, sans-serif; color: #555; }}
        .invoice-box table {{ width: 100%; line-height: inherit; text-align: left; }}
        .invoice-box table td {{ padding: 5px; vertical-align: top; }}
        .invoice-box table tr td:nth-child(2) {{ text-align: right; }}
        .invoice-box table tr.top table td {{ padding-bottom: 20px; }}
        .invoice-box table tr.information table td {{ padding-bottom: 40px; }}
        .invoice-box table tr.heading td {{ background: #eee; border-bottom: 1px solid #ddd; font-weight: bold; }}
        .invoice-box table tr.details td {{ padding-bottom: 20px; }}
        .invoice-box table tr.item td {{ border-bottom: 1px solid #eee; }}
        .invoice-box table tr.item.last td {{ border-bottom: none; }}
        .invoice-box table tr.total td:nth-child(2) {{ border-top: 2px solid #eee; font-weight: bold; }}
    </style>
    <div class="invoice-box">
        <table cellpadding="0" cellspacing="0">
            <tr class="top">
                <td colspan="2">
                    <table>
                        <tr>
                            <td style="width: 50%;">
                                <h2>AASHISH PHARMACY</h2>
                                <div>Manufacturing & Supply of Precision Press Tool & Room Component</div>
                                <div>64, Akshay Industrial Estate, Near New Cloath Market, Ahmedabad - 38562</div>
                                <div>Tel: 079-25820309</div>
                                <div>Web: www.aashishpharmacy.com</div>
                                <div>Email: info@aashishpharmacy.com</div>
                            </td>
                            <td style="width: 50%; text-align: right;">
                                <h2>TAX INVOICE</h2>
                                <div>GSTIN: 24HDE7487RE5RT4</div>
                                <div>Invoice No: {invoice_no}</div>
                                <div>Date: {date.today().strftime('%d-%m-%Y')}</div>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            <tr class="information">
                <td colspan="2">
                    <table>
                        <tr>
                            <td>
                                <strong>Customer Details:</strong><br>
                                Name: {customer_name}<br>
                                Phone: {customer_phone}<br>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            <tr class="heading">
                <td>Product Name</td>
                <td>Qty</td>
                <td>Manufacturer</td>
                <td>Batch Number</td>
                <td>Expiry</td>
                <td>Rate</td>
                <td>Total</td>
            </tr>
            {items_html}
            <tr class="total">
                <td colspan="5"></td>
                <td>Total:</td>
                <td>₹ {total_value:.2f}</td>
            </tr>
            <tr>
                <td colspan="7">Total in words: {num2words(int(total_value), lang='en_IN').title()} Rupees Only</td>
            </tr>
        </table>
    </div>
    """
    return html

def display_inventory():
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    
    # Custom CSS to force full width
    st.markdown("""
    <style>
    .stDataFrame, .stDataFrame > div, .stDataFrame > div > div {
        width: 100% !important;
    }
    .stDataFrame table {
        width: 100% !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Calculate a dynamic height based on the number of rows (e.g., 35 pixels per row + 40 for header)
    height = len(df) * 35 + 40
    
    # Set a minimum height of 400 pixels
    height = max(height, 400)
    
    st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        height=height
    )

def add_edit_inventory():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        medicine_name = st.text_input("Medicine Name")
        quantity = st.number_input("Quantity Available", min_value=0)
        manufacturer = st.text_input("Manufacturer")
    
    with col2:
        supplier = st.text_input("Supplier")
        supplier_price = st.number_input("Supplier Price", min_value=0.0)
        batch_no = st.text_input("Batch No.")
    
    with col3:
        exp_mfg_date = st.date_input("Exp/Mfg Date")
        amount = st.number_input("Amount", min_value=0.0)
        paid = st.checkbox("Paid")

    if st.button("Add/Update Item"):
        add_update_item(medicine_name, quantity, manufacturer, supplier, supplier_price, batch_no, exp_mfg_date, amount, paid)

def add_new_column(column_name, column_type):
    try:
        c.execute(f"ALTER TABLE inventory ADD COLUMN {column_name} {column_type}")
        conn.commit()
        st.success(f"Added new column: {column_name}")
    except sqlite3.OperationalError:
        st.error("Column already exists or invalid column name/type")

def add_update_item(medicine_name, quantity, manufacturer, supplier, supplier_price, batch_no, exp_mfg_date, amount, paid):
    c.execute('''INSERT OR REPLACE INTO inventory 
                 (medicine_name, quantity, manufacturer, supplier, supplier_price, batch_no, exp_mfg_date, amount, paid) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (medicine_name, quantity, manufacturer, supplier, supplier_price, batch_no, exp_mfg_date, amount, paid))
    conn.commit()
    st.success("Item added/updated successfully")

def edit_existing_product():
    # Fetch all product names
    c.execute("SELECT DISTINCT medicine_name FROM inventory")
    products = [row[0] for row in c.fetchall()]
    
    selected_product = st.selectbox("Select Product to Edit", products)
    
    if selected_product:
        # Fetch the selected product's details
        c.execute("SELECT * FROM inventory WHERE medicine_name = ?", (selected_product,))
        product_details = c.fetchone()
        
        if product_details:
            st.write(f"Editing: {selected_product}")
            
            # Create input fields with current values
            medicine_name = st.text_input("Medicine Name", value=product_details[1])
            quantity = st.number_input("Quantity Available", value=product_details[2], min_value=0)
            manufacturer = st.text_input("Manufacturer", value=product_details[3])
            supplier = st.text_input("Supplier", value=product_details[4])
            supplier_price = st.number_input("Supplier Price", value=product_details[5], min_value=0.0)
            batch_no = st.text_input("Batch No.", value=product_details[6])
            exp_mfg_date = st.date_input("Exp/Mfg Date", value=datetime.strptime(product_details[7], '%Y-%m-%d').date())
            amount = st.number_input("Amount", value=product_details[8], min_value=0.0)
            paid = st.checkbox("Paid", value=product_details[9])
            
            if st.button("Update Product"):
                update_product(product_details[0], medicine_name, quantity, manufacturer, supplier, supplier_price, batch_no, exp_mfg_date, amount, paid)
                st.success("Product updated successfully!")
                st.session_state.show_edit_popup = False
                st.experimental_rerun()
        else:
            st.error("Product not found in the database.")
    
    if st.button("Close"):
        st.session_state.show_edit_popup = False
        st.experimental_rerun()

def update_product(id, medicine_name, quantity, manufacturer, supplier, supplier_price, batch_no, exp_mfg_date, amount, paid):
    c.execute('''UPDATE inventory 
                 SET medicine_name=?, quantity=?, manufacturer=?, supplier=?, supplier_price=?, 
                     batch_no=?, exp_mfg_date=?, amount=?, paid=?
                 WHERE id=?''',
              (medicine_name, quantity, manufacturer, supplier, supplier_price, batch_no, exp_mfg_date, amount, paid, id))
    conn.commit()

def main():
    st.set_page_config(layout="wide")  # Set the page to wide mode
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Inventory Management", "Invoice Generator"])

    if page == "Inventory Management":
        inventory_management()
    elif page == "Invoice Generator":
        invoice_generator()

if __name__ == "__main__":
    if 'show_edit_popup' not in st.session_state:
        st.session_state.show_edit_popup = False
    main()