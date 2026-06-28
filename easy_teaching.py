from ast import BitAnd
from ctypes import pythonapi
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
import threading
import time
from plyer import notification 

notifications_enabled = True  # default ON

def toggle_notifications(btn):
    global notifications_enabled
    notifications_enabled = not notifications_enabled
    if notifications_enabled:
        btn.config(text="🔔")  # bell ON
        notification.notify(
            title="Class Reminder",
            message="Class starts in 30 minutes",
            timeout=10
        )
    else:
        btn.config(text="🔕")  # bell OFF

def logout(window):
    """Close main app window and return to login screen"""
    window.destroy()
    root.deiconify()  # show login window again

# ======================
# DATABASE CONFIG
# ======================
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',
    'database': 'schoolDB'
}

def create_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        messagebox.showerror("Database Error", f"Failed to connect to database:\n{e}")
        return None

def validate_login(username, password):
    connection = create_db_connection()
    if connection is None:
        return False
    try:
        cursor = connection.cursor()
        query = "SELECT * FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        return cursor.fetchone() is not None
    except Error as e:
        messagebox.showerror("Database Error", f"Login query failed:\n{e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

notified_tasks = set()
notified_classes = set()
reminder_started = False  

def task_reminder():
    if not notifications_enabled:
        return
    conn = create_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            cursor.execute("SELECT task_name FROM tasks WHERE deadline = %s AND status != 'Completed'", (tomorrow,))
            tasks_due = [row["task_name"] for row in cursor.fetchall()]
            for task in tasks_due:
                if task not in notified_tasks:
                    notification.notify(
                        title="Task Reminder",
                        message=f"{task} is due tomorrow",
                        timeout=10
                    )
                    notified_tasks.add(task)
        except Exception as e:
            print("Task reminder error:", e)
        finally:
            cursor.close()
            conn.close()


def class_reminder():
    if not notifications_enabled:
        return
    conn = create_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            today = datetime.now().strftime("%A")
            now = datetime.now()
            cursor.execute("SELECT subject, time FROM timetable WHERE day = %s", (today,))
            
            for row in cursor.fetchall():
                start_time_str = row['time'].split('-')[0]
                start_time = datetime.strptime(start_time_str, "%H:%M").replace(
                    year=now.year, month=now.month, day=now.day
                )

                # FIXED: stable key
                key = f"{row['subject']}_{start_time_str}_{today}"

                if 0 <= (start_time - now).total_seconds() <= 1800 and key not in notified_classes:
                    notification.notify(
                        title="Class Reminder",
                        message=f"{row['subject']} starts within the next 30 minutes",
                        timeout=10
                    )
                    notified_classes.add(key)  # FIXED: add to set

        except Exception as e:
            print("Class reminder error:", e)
        finally:
            cursor.close()
            conn.close()


def start_reminders():
    global reminder_started
    if reminder_started:
        return  # FIXED: prevents multiple threads

    reminder_started = True

    def reminder_loop():
        while True:
            task_reminder()
            class_reminder()
            time.sleep(60)

    threading.Thread(target=reminder_loop, daemon=True).start()

#======================
# Dashboard
#======================
def show_dashboard_tab(content_frame):
    for widget in content_frame.winfo_children():
        widget.destroy()

    dashboard_frame = tk.Frame(content_frame, padx=20, pady=20, bg="#f7f7f7")
    dashboard_frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(dashboard_frame, text="Easy Teaching", font=("Arial", 18, "bold"), bg="#f7f7f7").pack(anchor="center", pady=10)

    # === TOP SECTION ===
    top_frame = tk.Frame(dashboard_frame, bg="#f7f7f7")
    top_frame.pack(fill=tk.X, pady=10)

    # ---- Today's Tasks ----
    today_frame = tk.LabelFrame(top_frame, text="Today's Tasks", font=("Arial", 12, "bold"), padx=10, pady=10, bg="white")
    today_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)

    # ---- Today's Classes ----
    upcoming_frame = tk.LabelFrame(top_frame, text="Today's Classes", font=("Arial", 12, "bold"), padx=10, pady=10, bg="white")
    upcoming_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)

    # === PENDING TASKS (BOTTOM SECTION) ===
    pending_frame = tk.LabelFrame(dashboard_frame, text="Pending Tasks", font=("Arial", 12, "bold"), padx=10, pady=10, bg="white")
    pending_frame.pack(fill=tk.BOTH, expand=True, pady=10)

    # Load tasks and classes from DB
    connection = create_db_connection()
    pending_tasks, today_tasks, today_classes = [], [], []
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)

            # Pending tasks
            cursor.execute("SELECT task_name FROM tasks WHERE deadline IS NULL OR deadline > CURDATE()")
            pending_tasks = [row["task_name"] for row in cursor.fetchall()]

            # Today's tasks
            cursor.execute("SELECT task_name FROM tasks WHERE deadline = CURDATE()")
            today_tasks = [row["task_name"] for row in cursor.fetchall()]

            # Today's classes from timetable
            cursor.execute("""
                SELECT subject 
                FROM timetable
                WHERE day = DAYNAME(CURDATE())
                ORDER BY time
            """)
            today_classes = [row["subject"] for row in cursor.fetchall()]

        except Error as e:
            messagebox.showerror("Database Error", f"Failed to load data:\n{e}")
        finally:
            cursor.close()
            connection.close()

    # Display Today's Tasks
    if today_tasks:
        for task in today_tasks:
            tk.Label(today_frame, text="• " + task, font=("Arial", 10), anchor="w", bg="white").pack(fill=tk.X, pady=2)
    else:
        tk.Label(today_frame, text="No tasks for today", font=("Arial", 10, "italic"), bg="white").pack()

    # Display Today's Classes
    if today_classes:
        for cls in today_classes:
            tk.Label(upcoming_frame, text="• " + cls, font=("Arial", 10), anchor="w", bg="white").pack(fill=tk.X, pady=2)
    else:
        tk.Label(upcoming_frame, text="No classes today", font=("Arial", 10, "italic"), bg="white").pack()

    # Display Pending Tasks
    if pending_tasks:
        for task in pending_tasks:
            tk.Label(pending_frame, text="• " + task, font=("Arial", 10), anchor="w", bg="white").pack(fill=tk.X, pady=2)
    else:
        tk.Label(pending_frame, text="No pending tasks", font=("Arial", 10, "italic"), bg="white").pack()

# ======================
# CLASSES TAB
# ======================
def show_classes_tab(content_frame):
    # Clear content
    for widget in content_frame.winfo_children():
        widget.destroy()

    tk.Label(content_frame, text="Classes", font=("Arial", 16, "bold")).pack(pady=10)

    # Frame for list
    frame = tk.Frame(content_frame)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    classes_list = tk.Listbox(frame, font=("Arial", 11),
                              yscrollcommand=scrollbar.set, selectbackground="#e6f3ff")
    classes_list.pack(fill=tk.BOTH, expand=True)
    scrollbar.config(command=classes_list.yview)

    # Fetch classes from DB
    connection = create_db_connection()
    db_classes = []
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT class_name FROM classes ORDER BY class_name")
            db_classes = [row[0] for row in cursor.fetchall()]
        except Error as e:
            messagebox.showerror("Database Error", f"Could not load classes:\n{e}")
        finally:
            cursor.close()
            connection.close()

    for cls in db_classes:
        classes_list.insert(tk.END, cls)

    # On double click → open units of that class
    def on_class_select(event):
        selection = classes_list.curselection()
        if selection:
            class_name = classes_list.get(selection[0])
            show_class_details(class_name, content_frame)

    classes_list.bind("<Double-Button-1>", on_class_select)


def show_class_details(class_name, content_frame):
    # Clear content
    for widget in content_frame.winfo_children():
        widget.destroy()

    # Header
    tk.Label(content_frame, text=f"{class_name} - Units",
             font=("Arial", 14, "bold")).pack(pady=10)

    # Find class_id
    connection = create_db_connection()
    class_id = None
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT class_id FROM classes WHERE class_name = %s", (class_name,))
            result = cursor.fetchone()
            if result:
                class_id = result[0]
        except Error as e:
            messagebox.showerror("Database Error", f"Error finding class:\n{e}")
        finally:
            cursor.close()
            connection.close()

    # Dictionary to map display numbers to actual unit_ids
    unit_id_map = {}

    # Units list
    frame = tk.Frame(content_frame)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    units_list = tk.Listbox(frame, font=("Arial", 11),
                            yscrollcommand=scrollbar.set, selectbackground="#e6f3ff")
    units_list.pack(fill=tk.BOTH, expand=True)
    scrollbar.config(command=units_list.yview)

    # Load units
    def load_units():
        units_list.delete(0, tk.END)
        unit_id_map.clear()  # Clear the mapping each time we reload
        
        if not class_id:
            return
            
        connection = create_db_connection()
        if connection:
            try:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT * FROM units WHERE class_id = %s ORDER BY unit_id", (class_id,))
                units = cursor.fetchall()
                
                # Use sequential numbering instead of database unit_id
                for i, unit in enumerate(units, start=1):
                    status = "✔" if unit['completed'] else "❌"
                    display_text = f"{i}. {unit['unit_name']} [{status}]"
                    units_list.insert(tk.END, display_text)
                    unit_id_map[i] = unit['unit_id']  # Map display number to actual unit_id
                    
            except Error as e:
                messagebox.showerror("Database Error", f"Error loading units:\n{e}")
            finally:
                cursor.close()
                connection.close()

    # Add Unit function
    def add_selected_unit():
        popup = tk.Toplevel()
        popup.title("Add Unit")
        tk.Label(popup, text="Unit Name:").pack(pady=5)
        entry = tk.Entry(popup, width=30)
        entry.pack(pady=5, padx=10)

        def save():
            name = entry.get().strip()
            if name:
                conn = create_db_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO units (class_id, unit_name) VALUES (%s, %s)", (class_id, name))
                    conn.commit()
                    cur.close()
                    conn.close()
            load_units()
            popup.destroy()

        tk.Button(popup, text="Save", command=save).pack(pady=10)

    # Edit Unit function
    def edit_selected_unit():
        selection = units_list.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a unit to edit")
            return
            
        display_number = selection[0] + 1  # Convert to 1-based indexing
        if display_number not in unit_id_map:
            messagebox.showwarning("Warning", "Invalid unit selection")
            return
            
        unit_id = unit_id_map[display_number]
        unit_text = units_list.get(selection[0])

        popup = tk.Toplevel()
        popup.title("Edit Unit")
        tk.Label(popup, text="Edit Unit Name:").pack(pady=5)
        entry = tk.Entry(popup, width=30)   
        entry.insert(0, unit_text.split(".")[1].split("[")[0].strip())
        entry.pack(pady=5, padx=10)

        def save():
            new_name = entry.get().strip()
            if new_name:
                conn = create_db_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE units SET unit_name=%s WHERE unit_id=%s", (new_name, unit_id))
                    conn.commit()
                    cur.close()
                    conn.close()
            load_units()
            popup.destroy()

        tk.Button(popup, text="Save", command=save).pack(pady=10)

    # Delete Unit function
    def delete_selected_unit():
        selection = units_list.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a unit to delete")
            return
            
        display_number = selection[0] + 1  # Convert to 1-based indexing
        if display_number not in unit_id_map:
            messagebox.showwarning("Warning", "Invalid unit selection")
            return
            
        unit_id = unit_id_map[display_number]

        if messagebox.askyesno("Confirm", "Delete this unit?"):
            conn = create_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM units WHERE unit_id=%s", (unit_id,))
                conn.commit()
                cur.close()
                conn.close()
            load_units()

    # Complete Unit function
    def complete_selected_unit():
        selection = units_list.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a unit to complete")
            return
            
        display_number = selection[0] + 1  # Convert to 1-based indexing
        if display_number not in unit_id_map:
            messagebox.showwarning("Warning", "Invalid unit selection")
            return
            
        unit_id = unit_id_map[display_number]

        conn = create_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("UPDATE units SET completed=TRUE WHERE unit_id=%s", (unit_id,))
            conn.commit()
            cur.close()
            conn.close()
        load_units()

    # Buttons (ONLY ONCE)
    button_frame = tk.Frame(content_frame)
    button_frame.pack(pady=10)

    tk.Button(button_frame, text="Add Unit", width=12,
              command=add_selected_unit).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Edit Unit", width=12,
              command=edit_selected_unit).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Delete Unit", width=12,
              command=delete_selected_unit).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Complete Unit", width=15,
              command=complete_selected_unit).pack(side=tk.LEFT, padx=5)

    # Back button (ONLY ONCE)
    tk.Button(content_frame, text="← Back", font=("Arial", 10),
              command=lambda: show_classes_tab(content_frame)).pack(pady=5)

    # Initial load
    load_units()
# ======================
# TIMETABLE TAB
# ======================
def show_timetable_tab(content_frame):
    # Clear previous content
    for widget in content_frame.winfo_children():
        widget.destroy()

    # Title
    tk.Label(content_frame, text="Weekly Timetable",
             font=("Arial", 16, "bold")).pack(pady=10)

    # Table frame
    table_frame = tk.Frame(content_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Headers
    headers = ["Day", "Time", "Subject"]
    for col, header in enumerate(headers):
        tk.Label(table_frame, text=header, font=("Arial", 12, "bold"),
                 borderwidth=1, relief="solid", width=20, anchor="center").grid(row=0, column=col, sticky="nsew")

    # Load timetable from DB
    connection = create_db_connection()
    timetable = []
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT day, time, subject
                FROM timetable
                ORDER BY FIELD(day, 'Monday','Tuesday','Wednesday','Thursday','Friday'), time
            """)
            timetable = cursor.fetchall()
        except Error as e:
            messagebox.showerror("Database Error", f"Could not load timetable:\n{e}")
        finally:
            cursor.close()
            connection.close()

    # Populate rows
    for row, entry in enumerate(timetable, start=1):
        tk.Label(table_frame, text=entry['day'], font=("Arial", 11),
                 borderwidth=1, relief="solid", width=20, anchor="center").grid(row=row, column=0, sticky="nsew")
        tk.Label(table_frame, text=entry['time'], font=("Arial", 11),
                 borderwidth=1, relief="solid", width=20, anchor="center").grid(row=row, column=1, sticky="nsew")
        tk.Label(table_frame, text=entry['subject'], font=("Arial", 11),
                 borderwidth=1, relief="solid", width=50, anchor="w").grid(row=row, column=2, sticky="nsew")

    # Stretchable columns
    for col in range(3):
        table_frame.grid_columnconfigure(col, weight=1)

# ======================
# TASKS TAB
# ======================

def show_tasks_tab(content_frame):
    import tkinter as tk
    from tkinter import messagebox
    from datetime import datetime
    # Assumes create_db_connection() and Error (mysql.connector.Error) are defined elsewhere

    # Clear previous content
    for widget in content_frame.winfo_children():
        widget.destroy()

    # Keep a mapping: UI display number -> real DB task_id
    task_id_map = {}

    # Title
    tk.Label(content_frame, text="Tasks", font=("Arial", 16, "bold")).pack(pady=10)

    # Listbox with scrollbar
    list_frame = tk.Frame(content_frame)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    task_listbox = tk.Listbox(
        list_frame,
        yscrollcommand=scrollbar.set,
        font=("Arial", 11),
        selectbackground="#e6f3ff"
    )
    task_listbox.pack(fill=tk.BOTH, expand=True)
    scrollbar.config(command=task_listbox.yview)

    # Load tasks from DB (builds task_id_map so UI numbering is independent of task_id)
    def load_tasks():
        task_listbox.delete(0, tk.END)
        task_id_map.clear()
        conn = create_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT task_id, task_name, deadline, status FROM tasks ORDER BY deadline ASC")
                rows = cur.fetchall()
                for i, row in enumerate(rows, start=1):
                    task_id, name, deadline, status = row
                    if isinstance(deadline, datetime):
                        deadline_str = deadline.strftime("%Y-%m-%d")
                    else:
                        # if fetched as date object, handle that
                        try:
                            deadline_str = deadline.strftime("%Y-%m-%d")
                        except:
                            deadline_str = str(deadline) if deadline is not None else "N/A"
                    display = f"{i}. {name} (Due: {deadline_str}) [{status}]"
                    task_listbox.insert(tk.END, display)
                    task_id_map[i] = task_id
                cur.close()
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to load tasks:\n{e}")
            finally:
                try:
                    conn.close()
                except:
                    pass

    # ---------------- Add Task ----------------
    def add_task_popup():
        popup = tk.Toplevel(content_frame)
        popup.title("Add Task")
        popup.geometry("360x170")
        popup.transient(content_frame)
        popup.grab_set()

        tk.Label(popup, text="Task:").pack(pady=(10, 2), padx=12, anchor="w")
        entry = tk.Entry(popup, width=30)
        entry.pack(pady=2, padx=12)

        tk.Label(popup, text="Deadline (YYYY-MM-DD):").pack(pady=(8, 2), padx=12, anchor="w")
        deadline_entry = tk.Entry(popup, width=20)
        deadline_entry.pack(pady=2, padx=12)

        def save_task():
            task_name = entry.get().strip()
            deadline_text = deadline_entry.get().strip()
            if not task_name or not deadline_text:
                messagebox.showwarning("Input Error", "Please fill all fields", parent=popup)
                return
            try:
                deadline_date = datetime.strptime(deadline_text, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Input Error", "Deadline must be YYYY-MM-DD", parent=popup)
                return
            conn = create_db_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("INSERT INTO tasks (task_name, deadline, status) VALUES (%s, %s, 'Pending')",
                                (task_name, deadline_date))
                    conn.commit()
                    cur.close()
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to add task:\n{e}", parent=popup)
                finally:
                    try:
                        conn.close()
                    except:
                        pass
            load_tasks()
            popup.destroy()

        tk.Button(popup, text="Save", width=12, command=save_task).pack(pady=10)
        entry.focus_set()
        popup.wait_window()

    # ---------------- Edit Task ----------------
    def edit_task_popup():
        selection = task_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Error", "Select a task to edit")
            return
        index = selection[0]
        task_text = task_listbox.get(index)
        # UI number is before the first dot, e.g. "3. TaskName ..."
        try:
            display_number = int(task_text.split(".")[0])
        except:
            messagebox.showerror("Parse Error", "Could not determine selected task id")
            return
        if display_number not in task_id_map:
            messagebox.showerror("Mapping Error", "Could not find DB id for that task")
            return
        task_id = task_id_map[display_number]

        # Fetch current data
        conn = create_db_connection()
        if not conn:
            messagebox.showerror("Database Error", "Cannot connect to database")
            return
        try:
            cur = conn.cursor()
            cur.execute("SELECT task_name, deadline FROM tasks WHERE task_id = %s", (task_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if not row:
                messagebox.showerror("Error", "Task not found in database")
                return
            task_name, deadline = row
        except Exception as e:
            messagebox.showerror("Database Error", f"Error fetching task:\n{e}")
            try:
                conn.close()
            except:
                pass
            return

        popup = tk.Toplevel(content_frame)
        popup.title("Edit Task")
        popup.geometry("360x170")
        popup.transient(content_frame)
        popup.grab_set()

        tk.Label(popup, text="Task:").pack(pady=(10, 2), padx=12, anchor="w")
        entry = tk.Entry(popup, width=30)
        entry.insert(0, task_name)
        entry.pack(pady=2, padx=12)

        tk.Label(popup, text="Deadline (YYYY-MM-DD):").pack(pady=(8, 2), padx=12, anchor="w")
        deadline_entry = tk.Entry(popup, width=20)
        try:
            deadline_entry.insert(0, deadline.strftime("%Y-%m-%d"))
        except:
            deadline_entry.insert(0, str(deadline) if deadline is not None else "")
        deadline_entry.pack(pady=2, padx=12)

        def save_changes():
            new_name = entry.get().strip()
            new_deadline_text = deadline_entry.get().strip()
            if not new_name or not new_deadline_text:
                messagebox.showwarning("Input Error", "Please fill all fields", parent=popup)
                return
            try:
                new_deadline_date = datetime.strptime(new_deadline_text, "%Y-%m-%d").date()
            except ValueError:
                messagebox.showerror("Input Error", "Deadline must be YYYY-MM-DD", parent=popup)
                return
            conn = create_db_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute("UPDATE tasks SET task_name=%s, deadline=%s WHERE task_id=%s",
                                (new_name, new_deadline_date, task_id))
                    conn.commit()
                    cur.close()
                except Exception as e:
                    messagebox.showerror("Database Error", f"Failed to update task:\n{e}", parent=popup)
                finally:
                    try:
                        conn.close()
                    except:
                        pass
            load_tasks()
            popup.destroy()

        tk.Button(popup, text="Save", width=12, command=save_changes).pack(pady=10)
        entry.focus_set()
        popup.wait_window()

    # ---------------- Delete Task ----------------
    def delete_task():
        selection = task_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Error", "Select a task to delete")
            return
        index = selection[0]
        task_text = task_listbox.get(index)
        try:
            display_number = int(task_text.split(".")[0])
        except:
            messagebox.showerror("Parse Error", "Could not determine selected task id")
            return
        if display_number not in task_id_map:
            messagebox.showerror("Mapping Error", "Could not find DB id for that task")
            return
        task_id = task_id_map[display_number]

        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this task?"):
            return
        conn = create_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM tasks WHERE task_id=%s", (task_id,))
                conn.commit()
                cur.close()
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to delete task:\n{e}")
            finally:
                try:
                    conn.close()
                except:
                    pass
        load_tasks()

    # ---------------- Mark Complete ----------------
    def complete_task():
        selection = task_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Error", "Select a task to complete")
            return
        index = selection[0]
        task_text = task_listbox.get(index)
        try:
            display_number = int(task_text.split(".")[0])
        except:
            messagebox.showerror("Parse Error", "Could not determine selected task id")
            return
        if display_number not in task_id_map:
            messagebox.showerror("Mapping Error", "Could not find DB id for that task")
            return
        task_id = task_id_map[display_number]

        conn = create_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("UPDATE tasks SET status='Completed' WHERE task_id=%s", (task_id,))
                conn.commit()
                cur.close()
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to mark complete:\n{e}")
            finally:
                try:
                    conn.close()
                except:
                    pass
        load_tasks()

    # Buttons
    button_frame = tk.Frame(content_frame)
    button_frame.pack(fill=tk.X, pady=10)

    tk.Button(button_frame, text="Add Task", width=12, command=add_task_popup).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Edit Task", width=12, command=edit_task_popup).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Delete Task", width=12, command=delete_task).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Complete Task", width=12, command=complete_task).pack(side=tk.LEFT, padx=5)

    # Initial load
    load_tasks()
    
# ======================
# MAIN APP
# ======================
def sidebar_button_click(button_text, content_frame):
    if button_text == "Dashboard":
        show_dashboard_tab(content_frame)
    elif button_text == "Classes":
        show_classes_tab(content_frame)
    elif button_text == "Timetable":
        show_timetable_tab(content_frame)
    elif button_text == "Tasks":
        show_tasks_tab(content_frame)
    else:
        messagebox.showinfo("Menu", f"{button_text} section clicked")

def profile_button_click():
    messagebox.showinfo("Profile", "Profile options would appear here")

def notification_button_click():
    messagebox.showinfo("Notifications", "No new notifications")

def on_main_app_close(window):
    window.destroy()
    root.destroy()

def login():
    username = username_entry.get()
    password = password_entry.get()
    if not username or not password:
        messagebox.showwarning("Input Error", "Please enter both username and password")
        return
    if validate_login(username, password):
        # Save username if Remember Me is checked
        if remember_var.get():
            with open(REMEMBER_ME_FILE, "w") as f:
                f.write(username)
        else:
            # Remove saved username if unchecked
            if os.path.exists(REMEMBER_ME_FILE):
                os.remove(REMEMBER_ME_FILE)

        root.withdraw()
        show_main_app()
    else:
        messagebox.showerror("Login Failed", "Invalid username or password")


def show_main_app():
    global notifications_enabled

    main_app = tk.Toplevel()
    main_app.title("Easy Teaching")
    main_app.geometry("1200x700")
    main_app.minsize(1000, 600)

    # ================= SIDEBAR =================
    sidebar = tk.Frame(main_app, bg="#f0f0f0", width=200, relief=tk.RIDGE, borderwidth=1)
    sidebar.pack(side=tk.LEFT, fill=tk.Y)

    content = tk.Frame(main_app)
    content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    buttons = ["Dashboard", "Classes", "Timetable", "Tasks"]
    for btn_text in buttons:
        btn = tk.Button(
            sidebar,
            text=btn_text,
            bg="#f0f0f0",
            relief=tk.FLAT,
            font=("Arial", 10),
            command=lambda t=btn_text: sidebar_button_click(t, tab_frame)
        )
        btn.pack(fill=tk.X, padx=5, pady=2, anchor=tk.W)

    # ================= LOGOUT BUTTON AT BOTTOM =================
    logout_btn = tk.Button(
        sidebar,
        text="Logout",
        font=("Arial", 10, "bold"),
        bg="#ff4d4d",
        fg="white",
        relief=tk.FLAT,
        command=lambda: logout(main_app)
    )
    logout_btn.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=10)

    # ================= TOP BAR =================
    top_bar = tk.Frame(content, bg="#ffffff", relief=tk.RIDGE, borderwidth=1)
    top_bar.pack(fill=tk.X)

    # Title on the left
    title_lbl = tk.Label(
        top_bar,
        text="",
        font=("Arial", 12, "bold"),
        bg="#ffffff"
    )
    title_lbl.pack(side=tk.LEFT, padx=10, pady=5)

    # Frame for buttons on the right (logout + bell)
    right_btns = tk.Frame(top_bar, bg="#ffffff")
    right_btns.pack(side=tk.RIGHT, padx=10, pady=5)

    # Notification bell
    notif_btn = tk.Button(
        right_btns,
        text="🔔" if notifications_enabled else "🔕",
        font=("Arial", 12),
        relief=tk.FLAT,
        command=lambda: toggle_notifications(notif_btn)
    )
    notif_btn.pack(side=tk.RIGHT, padx=5)

    # ================= TAB FRAME =================
    tab_frame = tk.Frame(content, bg="#fdfdfd")
    tab_frame.pack(fill=tk.BOTH, expand=True)

    # ================= SHOW DASHBOARD =================
    show_dashboard_tab(tab_frame)

    # ================= START REMINDERS =================
    start_reminders()  # background thread

    # ================= HANDLE CLOSING =================
    def on_close():
        main_app.destroy()
        root.destroy()

    main_app.protocol("WM_DELETE_WINDOW", on_close)

# ======================
# LOGIN WINDOW
# ======================
root = tk.Tk()
root.title("Login")
root.geometry("400x300")
root.eval('tk::PlaceWindow . center') 

import os

# Remember Me Function
REMEMBER_ME_FILE = "remember_me.txt"

# Check if a username was saved
if os.path.exists(REMEMBER_ME_FILE):
    with open(REMEMBER_ME_FILE, "r") as f:
        saved_username = f.read().strip()
else:
    saved_username = ""

tk.Label(root, text="Username", font=("Arial", 10)).pack(pady=5)
username_entry = tk.Entry(root, font=("Arial", 10))
username_entry.pack(pady=5)
username_entry.insert(0, saved_username)

tk.Label(root, text="Password", font=("Arial", 10)).pack(pady=5)
password_entry = tk.Entry(root, show="*", font=("Arial", 10))
password_entry.pack(pady=5)

remember_var = tk.BooleanVar(value=bool(saved_username))
tk.Checkbutton(root, text="Remember me?", font=("Arial", 9), variable=remember_var).pack(pady=5)
tk.Button(root, text="Login", command=login, font=("Arial", 10), width=10).pack(pady=10)

root.mainloop()