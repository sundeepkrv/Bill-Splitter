import os
import sqlite3
import secrets
import heapq
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "super_secret_bill_splitter_2026"
DATABASE = "billSplitter.db"

def get_db():
	conn = sqlite3.connect(DATABASE)
	conn.row_factory = sqlite3.Row
	return conn

def init_db():
	with get_db() as conn:
		conn.execute('''CREATE TABLE IF NOT EXISTS groups (
							id TEXT PRIMARY KEY,
							name TEXT NOT NULL UNIQUE)''')
		conn.execute('''CREATE TABLE IF NOT EXISTS members (
							id INTEGER PRIMARY KEY AUTOINCREMENT,
							group_id TEXT,
							name TEXT NOT NULL,
							FOREIGN KEY(group_id) REFERENCES groups(id),
							UNIQUE(group_id, name))''')
		conn.execute('''CREATE TABLE IF NOT EXISTS expenses (
							id INTEGER PRIMARY KEY AUTOINCREMENT,
							group_id TEXT,
							description TEXT NOT NULL,
							total_amount INTEGER NOT NULL,
							split_type TEXT NOT NULL,
							FOREIGN KEY(group_id) REFERENCES groups(id))''')
		conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
							id INTEGER PRIMARY KEY AUTOINCREMENT,
							group_id TEXT,
							expense_id INTEGER, 
							member_name TEXT NOT NULL,
							amount INTEGER NOT NULL, 
							type TEXT NOT NULL,   
							FOREIGN KEY(group_id) REFERENCES groups(id),
							FOREIGN KEY(expense_id) REFERENCES expenses(id) ON DELETE CASCADE)''')
		conn.commit()

def get_group_details(group_id):
	conn = get_db()
	active_group = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
	if not active_group:
		return None, None, None, None, None, None
		
	members = conn.execute("SELECT * FROM members WHERE group_id = ?", (group_id,)).fetchall()
	expenses = conn.execute("SELECT * FROM expenses WHERE group_id = ?", (group_id,)).fetchall()
	
	settlements = conn.execute(
		"SELECT DISTINCT t1.id, t1.member_name AS payer, abs(t1.amount) AS amount, t2.member_name AS receiver "
		"FROM transactions t1 JOIN transactions t2 ON t1.group_id = t2.group_id "
		"WHERE t1.group_id = ? AND t1.type = 'SETTLEMENT' AND t1.amount > 0 AND t2.type = 'SETTLEMENT' AND t2.amount < 0 "
		"AND t1.id = t2.id - 1", (group_id,)
	).fetchall()

	expenses_with_details = []
	for exp in expenses:
		payers = conn.execute("SELECT member_name, amount FROM transactions WHERE expense_id = ? AND type = 'PAYMENT'", (exp['id'],)).fetchall()
		shares = conn.execute("SELECT member_name, amount FROM transactions WHERE expense_id = ? AND type = 'DEBIT'", (exp['id'],)).fetchall()
		expenses_with_details.append({
			'id': exp['id'],
			'description': exp['description'],
			'total_amount': int(exp['total_amount']),
			'split_type': exp['split_type'],
			'payers': {p['member_name']: int(p['amount']) for p in payers},
			'shares': {s['member_name']: int(abs(s['amount'])) for s in shares}
		})
	
	balances = get_net_balances(group_id)
	simplified_debts = calculate_simplified_debts(balances)
	return active_group, members, expenses_with_details, settlements, balances, simplified_debts

def get_net_balances(group_id):
	conn = get_db()
	cursor = conn.execute("SELECT name FROM members WHERE group_id = ?", (group_id,))
	members = [row['name'] for row in cursor.fetchall()]
	balances = {name: 0 for name in members}
	
	cursor = conn.execute(
		"SELECT member_name, SUM(amount) as net FROM transactions WHERE group_id = ? GROUP BY member_name", 
		(group_id,)
	)
	for row in cursor.fetchall():
		if row['member_name'] in balances:
			balances[row['member_name']] = int(row['net'])
	return balances

def calculate_simplified_debts(balances):
	debtors, creditors = [], []
	for member, balance in balances.items():
		if balance < 0:
			heapq.heappush(debtors, (balance, member))
		elif balance > 0:
			heapq.heappush(creditors, (-balance, member))

	simplified = []
	while debtors and creditors:
		deb_bal, debtor = heapq.heappop(debtors)
		cred_bal, creditor = heapq.heappop(creditors)
		cred_bal = -cred_bal

		settle_amount = min(abs(deb_bal), cred_bal)
		simplified.append({'from': debtor, 'to': creditor, 'amount': int(round(settle_amount))})

		remaining_deb = deb_bal + settle_amount
		remaining_cred = cred_bal - settle_amount

		if remaining_deb < 0:
			heapq.heappush(debtors, (remaining_deb, debtor))
		if remaining_cred > 0:
			heapq.heappush(creditors, (-remaining_cred, creditor))
	return simplified

@app.route('/')
def index():
	return render_template('dashboard.html', groups=[], active_group=None)

@app.route('/group/<string:group_id>')
def view_group(group_id):
	conn = get_db()
	groups = conn.execute("SELECT * FROM groups").fetchall()
	
	active_group, members, expenses, settlements, balances, simplified_debts = get_group_details(group_id)
	if not active_group:
		flash("Group not found!", "error")
		return redirect(url_for('index'))
		
	return render_template(
		'dashboard.html', 
		groups=groups, 
		active_group=active_group,
		members=members,
		expenses=expenses,
		settlements=settlements,
		balances=balances,
		simplified_debts=simplified_debts
	)

@app.route('/share/<string:group_id>')
def share_preview(group_id):
	active_group, members, expenses, settlements, balances, simplified_debts = get_group_details(group_id)
	if not active_group:
		flash("This share link is invalid or has expired.", "error")
		return redirect(url_for('index'))
		
	return render_template(
		'share.html',
		active_group=active_group,
		balances=balances,
		settlements=settlements,
		simplified_debts=simplified_debts
	)

@app.route('/add_group', methods=['POST'])
def add_group():
	name = request.form.get('name').strip()
	if name:
		try:
			conn = get_db()
			random_id = secrets.token_hex(8)
			conn.execute("INSERT INTO groups (id, name) VALUES (?, ?)", (random_id, name))
			conn.commit()
			flash(f"Group '{name}' created successfully!", "success")
			return redirect(url_for('view_group', group_id=random_id))
		except sqlite3.IntegrityError:
			flash("A group with that name already exists!", "error")
	return redirect(url_for('index'))

@app.route('/group/<string:group_id>/rename', methods=['POST'])
def rename_group(group_id):
	new_group_name = request.form.get('new_group_name').strip()
	if new_group_name:
		try:
			conn = get_db()
			conn.execute("UPDATE groups SET name = ? WHERE id = ?", (new_group_name, group_id))
			conn.commit()
			flash(f"Group renamed to '{new_group_name}' successfully!", "success")
		except sqlite3.IntegrityError:
			flash("That group name is already taken.", "error")
	return redirect(url_for('view_group', group_id=group_id))

@app.route('/group/<string:group_id>/edit_member/<int:member_id>', methods=['POST'])
def edit_member(group_id, member_id):
	new_name = request.form.get('new_name').strip()
	if new_name:
		conn = get_db()
		old_name_row = conn.execute("SELECT name FROM members WHERE id = ?", (member_id,)).fetchone()
		if old_name_row:
			old_name = old_name_row['name']
			try:
				conn.execute("UPDATE members SET name = ? WHERE id = ?", (new_name, member_id))
				conn.execute("UPDATE transactions SET member_name = ? WHERE group_id = ? AND member_name = ?", (new_name, group_id, old_name))
				conn.commit()
				flash(f"Name updated to: {new_name}", "success")
			except sqlite3.IntegrityError:
				flash("This name already exists in the group.", "error")
	return redirect(url_for('view_group', group_id=group_id))

@app.route('/group/<string:group_id>/add_member', methods=['POST'])
def add_member(group_id):
	name = request.form.get('name').strip()
	if name:
		try:
			conn = get_db()
			conn.execute("INSERT INTO members (group_id, name) VALUES (?, ?)", (group_id, name))
			conn.commit()
			flash(f"Added member: {name}", "success")
		except sqlite3.IntegrityError:
			flash("This person is already in the group.", "error")
	return redirect(url_for('view_group', group_id=group_id))

@app.route('/group/<string:group_id>/process_expense', methods=['POST'])
def process_expense(group_id):
	expense_id = request.form.get('expense_id') 
	description = request.form.get('description')
	total_amount = int(round(float(request.form.get('total_amount'))))
	split_type = request.form.get('split_type')
	
	conn = get_db()
	members = [m['name'] for m in conn.execute("SELECT name FROM members WHERE group_id = ?", (group_id,)).fetchall()]
	
	checked_payers = [m for m in members if request.form.get(f'payer_checked_{m}')]
	if not checked_payers:
		flash("Please select at least one person who paid!", "error")
		return redirect(url_for('view_group', group_id=group_id))
	
	base_payer_share = total_amount // len(checked_payers)
	remainder_payer_cents = total_amount % len(checked_payers)
	
	payers_data = {}
	for i, p in enumerate(checked_payers):
		payers_data[p] = base_payer_share + (1 if i < remainder_payer_cents else 0)

	shares = {}
	if split_type == 'EQUAL':
		selected_sharers = request.form.getlist('sharers_equal')
		if not selected_sharers:
			flash("Please select at least one person to split the bill with!", "error")
			return redirect(url_for('view_group', group_id=group_id))
			
		base_share = total_amount // len(selected_sharers)
		remainder = total_amount % len(selected_sharers)
		for i, s in enumerate(selected_sharers):
			shares[s] = base_share + (1 if i < remainder else 0)
			
	elif split_type == 'UNEQUAL':
		total_entered_shares = 0
		for m in members:
			amt = int(round(float(request.form.get(f'share_unequal_{m}', 0) or 0)))
			if amt > 0:
				shares[m] = amt
				total_entered_shares += amt
		if total_entered_shares != total_amount:
			flash(f"The amounts entered (₹{total_entered_shares}) do not match the total bill amount (₹{total_amount})", "error")
			return redirect(url_for('view_group', group_id=group_id))
			
	elif split_type == 'PERCENT':
		total_pct = 0.0
		running_share_sum = 0
		sorted_members_by_pct = []
		
		for m in members:
			pct = float(request.form.get(f'share_pct_{m}', 0) or 0)
			if pct > 0:
				total_pct += pct
				sorted_members_by_pct.append((pct, m))
				
		if abs(total_pct - 100.0) > 0.01:
			flash(f"Percentages must add up to 100%. Total is currently: {total_pct}%", "error")
			return redirect(url_for('view_group', group_id=group_id))
			
		for i, (pct, m) in enumerate(sorted_members_by_pct):
			if i == len(sorted_members_by_pct) - 1:
				shares[m] = total_amount - running_share_sum
			else:
				calculated_share = int(round((pct / 100.0) * total_amount))
				shares[m] = calculated_share
				running_share_sum += calculated_share

	if expense_id:
		conn.execute("UPDATE expenses SET description = ?, total_amount = ?, split_type = ? WHERE id = ?", (description, total_amount, split_type, expense_id))
		conn.execute("DELETE FROM transactions WHERE expense_id = ?", (expense_id,))
		active_expense_id = expense_id
	else:
		cursor = conn.execute("INSERT INTO expenses (group_id, description, total_amount, split_type) VALUES (?, ?, ?, ?)", 
							 (group_id, description, total_amount, split_type))
		active_expense_id = cursor.lastrowid
	
	for payer, amt in payers_data.items():
		conn.execute("INSERT INTO transactions (group_id, expense_id, member_name, amount, type) VALUES (?, ?, ?, ?, 'PAYMENT')", 
					 (group_id, active_expense_id, payer, amt))
					 
	for borrower, amt in shares.items():
		conn.execute("INSERT INTO transactions (group_id, expense_id, member_name, amount, type) VALUES (?, ?, ?, ?, 'DEBIT')", 
					 (group_id, active_expense_id, borrower, -amt))
					 
	conn.commit()
	flash("Expense saved successfully!", "success")
	return redirect(url_for('view_group', group_id=group_id))

@app.route('/group/<string:group_id>/delete_expense/<int:expense_id>', methods=['POST'])
def delete_expense(group_id, expense_id):
	conn = get_db()
	conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
	conn.execute("DELETE FROM transactions WHERE expense_id = ?", (expense_id,))
	conn.commit()
	flash("Expense deleted.", "success")
	return redirect(url_for('view_group', group_id=group_id))

@app.route('/group/<string:group_id>/delete_settlement/<int:settlement_id>', methods=['POST'])
def delete_settlement(group_id, settlement_id):
	conn = get_db()
	conn.execute("DELETE FROM transactions WHERE id IN (?, ?)", (settlement_id, settlement_id + 1))
	conn.commit()
	flash("Settlement record removed.", "success")
	return redirect(url_for('view_group', group_id=group_id))

@app.route('/group/<string:group_id>/settle', methods=['POST'])
def manual_settle(group_id):
	payer = request.form.get('payer')
	receiver = request.form.get('receiver')
	amount = int(round(float(request.form.get('amount'))))
	
	if payer == receiver:
		flash("A person cannot pay themselves.", "error")
		return redirect(url_for('view_group', group_id=group_id))
		
	conn = get_db()
	conn.execute("INSERT INTO transactions (group_id, member_name, amount, type) VALUES (?, ?, ?, 'SETTLEMENT')", (group_id, payer, amount))
	conn.execute("INSERT INTO transactions (group_id, member_name, amount, type) VALUES (?, ?, ?, 'SETTLEMENT')", (group_id, receiver, -amount))
	conn.commit()
	
	flash(f"Payment recorded: {payer} paid ₹{amount} to {receiver}", "success")
	return redirect(url_for('view_group', group_id=group_id))

if __name__ == '__main__':
	if not os.path.exists(DATABASE):
		init_db()
	app.run(debug=True, host='0.0.0.0')