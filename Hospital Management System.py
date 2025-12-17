import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- DATABASE SETUP ---

def db_connect():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect('hospital_full.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database(conn):
    """Creates the necessary tables if they don't already exist."""
    cursor = conn.cursor()
    # Department & Staff
    cursor.execute("CREATE TABLE IF NOT EXISTS Department (dept_id INTEGER PRIMARY KEY, dept_name TEXT NOT NULL UNIQUE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS Staff (staff_id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL)")
    # Doctor (with department link)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Doctor (
            doctor_id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL,
            contact_number TEXT, dept_id INTEGER,
            FOREIGN KEY (dept_id) REFERENCES Department(dept_id))
    """)
    # Patient & Appointment
    cursor.execute("CREATE TABLE IF NOT EXISTS Patient (patient_id INTEGER PRIMARY KEY, name TEXT NOT NULL, contact_number TEXT)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Appointment (
            appointment_id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL, appointment_time TEXT NOT NULL, status TEXT DEFAULT 'Scheduled',
            FOREIGN KEY (patient_id) REFERENCES Patient(patient_id), FOREIGN KEY (doctor_id) REFERENCES Doctor(doctor_id))
    """)
    # Ambulance
    cursor.execute("CREATE TABLE IF NOT EXISTS Ambulance (ambulance_id INTEGER PRIMARY KEY, vehicle_number TEXT NOT NULL UNIQUE, status TEXT DEFAULT 'Available')")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS AmbulanceBooking (
            booking_id INTEGER PRIMARY KEY, ambulance_id INTEGER NOT NULL UNIQUE, patient_id INTEGER NOT NULL,
            pickup_address TEXT, booking_time TEXT,
            FOREIGN KEY (ambulance_id) REFERENCES Ambulance(ambulance_id), FOREIGN KEY (patient_id) REFERENCES Patient(patient_id))
    """)
    # Pharmacy
    cursor.execute("CREATE TABLE IF NOT EXISTS Pharmacy (medicine_id INTEGER PRIMARY KEY, medicine_name TEXT NOT NULL UNIQUE, stock INTEGER NOT NULL)")
    conn.commit()

# --- HELPER & QUERY FUNCTIONS ---

def execute_query(conn, query, params=()):
    """Executes a write query (INSERT, UPDATE, DELETE)."""
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()

def get_data_as_df(conn, query, params=()):
    """Fetches data and returns it as a Pandas DataFrame."""
    return pd.read_sql_query(query, conn, params=params)

def get_names_dict(conn, table, id_col, name_col, where_clause="1=1"):
    """Fetches data as a dictionary {name: id} for select boxes."""
    query = f"SELECT {id_col}, {name_col} FROM {table} WHERE {where_clause}"
    df = get_data_as_df(conn, query)
    return {row[name_col]: row[id_col] for _, row in df.iterrows()}

def populate_ambulances(conn, total_ambulances):
    """Ensures the ambulance table has the specified number of vehicles."""
    current_count = conn.execute("SELECT COUNT(*) FROM Ambulance").fetchone()[0]
    if current_count < total_ambulances:
        for i in range(current_count + 1, total_ambulances + 1):
            execute_query(conn, "INSERT OR IGNORE INTO Ambulance (vehicle_number) VALUES (?)", (f"AMB-{i:03}",))


# --- MAIN APP UI ---

def main():
    st.set_page_config(page_title="Hospital Management System", layout="wide", page_icon="🏥")
    st.markdown("""<style> /* CSS for modern look */ </style>""", unsafe_allow_html=True)
    st.title("🏥 Hospital Management System")

    conn = db_connect()
    setup_database(conn)

    st.sidebar.title("Navigation")
    # Ambulance fleet size controller
    total_ambulances = st.sidebar.number_input("Total Ambulance Fleet", min_value=1, value=5, step=1)
    populate_ambulances(conn, total_ambulances)

    menu_options = ["Dashboard", "Staff", "Departments", "Doctors", "Patients", "Appointments", "Ambulance", "Pharmacy"]
    choice = st.sidebar.radio("Go to", menu_options)

    # --- DASHBOARD ---
    if choice == "Dashboard":
        st.header("Hospital Dashboard")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Staff", conn.execute("SELECT COUNT(*) FROM Staff").fetchone()[0])
        col2.metric("Total Doctors", conn.execute("SELECT COUNT(*) FROM Doctor").fetchone()[0])
        col3.metric("Total Patients", conn.execute("SELECT COUNT(*) FROM Patient").fetchone()[0])
        col4.metric("Available Ambulances", conn.execute("SELECT COUNT(*) FROM Ambulance WHERE status = 'Available'").fetchone()[0])
        st.subheader("Upcoming Appointments")
        st.dataframe(get_data_as_df(conn, """
            SELECT p.name AS Patient, d.name AS Doctor, a.appointment_date AS Date, a.appointment_time AS Time, a.status
            FROM Appointment a JOIN Patient p ON a.patient_id = p.patient_id JOIN Doctor d ON a.doctor_id = d.doctor_id
            WHERE a.appointment_date >= date('now') ORDER BY a.appointment_date, a.appointment_time LIMIT 10
        """), use_container_width=True)

    # --- STAFF ---
    elif choice == "Staff":
        st.header("Staff Management")
        with st.expander("➕ Add New Staff"):
            with st.form("staff_form", clear_on_submit=True):
                name = st.text_input("Staff Name")
                role = st.text_input("Role (e.g., Nurse, Receptionist)")
                if st.form_submit_button("Add Staff"):
                    execute_query(conn, "INSERT INTO Staff (name, role) VALUES (?, ?)", (name, role))
                    st.success(f"Staff member '{name}' added.")
        st.subheader("Current Staff")
        st.dataframe(get_data_as_df(conn, "SELECT staff_id AS ID, name, role FROM Staff"), use_container_width=True)

    # --- DEPARTMENTS ---
    elif choice == "Departments":
        st.header("Department Management")
        with st.expander("➕ Add New Department"):
            with st.form("dept_form", clear_on_submit=True):
                dept_name = st.text_input("Department Name")
                if st.form_submit_button("Add Department"):
                    execute_query(conn, "INSERT INTO Department (dept_name) VALUES (?)", (dept_name,))
                    st.success(f"Department '{dept_name}' added.")
        st.subheader("Hospital Departments")
        st.dataframe(get_data_as_df(conn, "SELECT dept_id AS ID, dept_name AS Department FROM Department"), use_container_width=True)

    # --- DOCTORS ---
    elif choice == "Doctors":
        st.header("Doctor Management")
        with st.expander("➕ Add New Doctor"):
            with st.form("doctor_form", clear_on_submit=True):
                depts = get_names_dict(conn, "Department", "dept_id", "dept_name")
                name = st.text_input("Name"); specialty = st.text_input("Specialty")
                dept_name = st.selectbox("Department", options=list(depts.keys()))
                if st.form_submit_button("Add Doctor"):
                    dept_id = depts.get(dept_name)
                    execute_query(conn, "INSERT INTO Doctor (name, specialty, dept_id) VALUES (?, ?, ?)", (name, specialty, dept_id))
                    st.success(f"Doctor '{name}' added.")
        st.subheader("Current Doctors")
        st.dataframe(get_data_as_df(conn, """
            SELECT d.doctor_id AS ID, d.name, d.specialty, IFNULL(p.dept_name, 'N/A') as Department
            FROM Doctor d LEFT JOIN Department p ON d.dept_id = p.dept_id
        """), use_container_width=True)

    # --- PATIENTS ---
    elif choice == "Patients":
        st.header("Patient Management")
        with st.expander("➕ Add New Patient"):
            with st.form("patient_form", clear_on_submit=True):
                name = st.text_input("Patient Name"); contact = st.text_input("Contact")
                if st.form_submit_button("Add Patient"):
                    execute_query(conn, "INSERT INTO Patient (name, contact_number) VALUES (?, ?)", (name, contact))
                    st.success(f"Patient '{name}' added.")
        st.subheader("Registered Patients")
        st.dataframe(get_data_as_df(conn, "SELECT patient_id AS ID, name, contact_number FROM Patient"), use_container_width=True)

    # --- APPOINTMENTS ---
    elif choice == "Appointments":
        st.header("Appointment Management")
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("🗓️ Schedule New Appointment"):
                with st.form("appt_form", clear_on_submit=True):
                    patients = get_names_dict(conn, "Patient", "patient_id", "name")
                    doctors = get_names_dict(conn, "Doctor", "doctor_id", "name")
                    patient_name = st.selectbox("Patient", list(patients.keys()))
                    doctor_name = st.selectbox("Doctor", list(doctors.keys()))
                    app_date = st.date_input("Date", min_value=datetime.today())
                    app_time = st.time_input("Time")
                    if st.form_submit_button("Schedule"):
                        execute_query(conn, "INSERT INTO Appointment (patient_id, doctor_id, appointment_date, appointment_time) VALUES (?, ?, ?, ?)",
                                      (patients[patient_name], doctors[doctor_name], app_date.strftime('%Y-%m-%d'), app_time.strftime('%H:%M:%S')))
                        st.success("Appointment scheduled.")
        with col2:
            with st.expander("❌ Cancel Appointment"):
                with st.form("cancel_appt_form", clear_on_submit=True):
                    appts = get_names_dict(conn, "Appointment", "appointment_id", "appointment_id", where_clause="status = 'Scheduled'")
                    appt_id = st.selectbox("Select Appointment ID to Cancel", list(appts.keys()))
                    if st.form_submit_button("Cancel Appointment"):
                        if appt_id:
                            execute_query(conn, "UPDATE Appointment SET status = 'Cancelled' WHERE appointment_id = ?", (appts[appt_id],))
                            st.warning(f"Appointment {appt_id} cancelled.")
        st.subheader("All Appointments")
        st.dataframe(get_data_as_df(conn, """
            SELECT a.appointment_id AS ID, p.name AS Patient, d.name AS Doctor, a.appointment_date, a.appointment_time, a.status
            FROM Appointment a JOIN Patient p ON a.patient_id = p.patient_id JOIN Doctor d ON a.doctor_id = d.doctor_id ORDER BY a.appointment_date DESC
        """), use_container_width=True)

    # --- AMBULANCE ---
    elif choice == "Ambulance":
        st.header("Ambulance Service 🚑")
        col1, col2 = st.columns(2)
        with col1:
            with st.expander("➕ Book an Ambulance"):
                with st.form("book_amb_form", clear_on_submit=True):
                    avail_ambs = get_names_dict(conn, "Ambulance", "ambulance_id", "vehicle_number", where_clause="status = 'Available'")
                    patients = get_names_dict(conn, "Patient", "patient_id", "name")
                    amb_v_num = st.selectbox("Available Ambulance", list(avail_ambs.keys()))
                    patient_name = st.selectbox("Patient", list(patients.keys()))
                    address = st.text_area("Pickup Address")
                    if st.form_submit_button("Book Ambulance"):
                        if amb_v_num and patient_name and address:
                            amb_id = avail_ambs[amb_v_num]
                            execute_query(conn, "UPDATE Ambulance SET status = 'In Use' WHERE ambulance_id = ?", (amb_id,))
                            execute_query(conn, "INSERT INTO AmbulanceBooking (ambulance_id, patient_id, pickup_address, booking_time) VALUES (?, ?, ?, ?)",
                                          (amb_id, patients[patient_name], address, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                            st.success(f"{amb_v_num} booked for {patient_name}.")
        with col2:
            with st.expander("❌ Cancel Ambulance Booking"):
                 with st.form("cancel_amb_form", clear_on_submit=True):
                    booked_ambs = get_names_dict(conn, "AmbulanceBooking", "ambulance_id", "ambulance_id")
                    booking_id = st.selectbox("Select Booking to Cancel (by Ambulance ID)", list(booked_ambs.keys()))
                    if st.form_submit_button("Cancel Booking"):
                        if booking_id:
                            amb_id_to_cancel = booked_ambs[booking_id]
                            execute_query(conn, "DELETE FROM AmbulanceBooking WHERE ambulance_id = ?", (amb_id_to_cancel,))
                            execute_query(conn, "UPDATE Ambulance SET status = 'Available' WHERE ambulance_id = ?", (amb_id_to_cancel,))
                            st.warning(f"Booking for Ambulance ID {booking_id} cancelled.")
        st.subheader("Ambulance Fleet Status")
        st.dataframe(get_data_as_df(conn, """
            SELECT a.vehicle_number, a.status, p.name AS Patient, ab.pickup_address
            FROM Ambulance a
            LEFT JOIN AmbulanceBooking ab ON a.ambulance_id = ab.ambulance_id
            LEFT JOIN Patient p ON ab.patient_id = p.patient_id
        """), use_container_width=True)

    # --- PHARMACY ---
    elif choice == "Pharmacy":
        st.header("Pharmacy Inventory 💊")
        with st.expander("➕ Add New Medicine"):
            with st.form("pharm_form", clear_on_submit=True):
                med_name = st.text_input("Medicine Name")
                stock = st.number_input("Initial Stock Quantity", min_value=0, step=1)
                if st.form_submit_button("Add Medicine"):
                    execute_query(conn, "INSERT INTO Pharmacy (medicine_name, stock) VALUES (?, ?)", (med_name, stock))
                    st.success(f"Added {med_name} to pharmacy.")
        st.subheader("Current Stock")
        st.dataframe(get_data_as_df(conn, "SELECT medicine_id AS ID, medicine_name, stock FROM Pharmacy"), use_container_width=True)

    conn.close()

if __name__ == "__main__":
    main()