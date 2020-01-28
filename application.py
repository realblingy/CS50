import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

quotes = []

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    stocks = db.execute("SELECT stocksymbol, price, stockprice,  SUM(quantity), SUM(price) FROM Transactions WHERE userid = :userid GROUP BY stocksymbol", userid=session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
    cash = cash[0]['cash']
    user_stocks = []
    total = cash;
    i = 0

    for stock in stocks:
        total += stocks[i]['SUM(price)']
        i += 1
        if lookup(stock['stocksymbol']) not in user_stocks and stock['SUM(quantity)'] > 0:
            user_stocks.append(stock)

    return render_template("index.html", stocks=user_stocks, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        quote = lookup(request.form.get("symbol"))
        try:
            int(request.form.get("shares"))
        except:
            return apology("Invalid quantity", 400)

        if not quote:
            return apology("Stock symbol does not exist", 400)
        elif int(request.form.get("shares")) < 0:
            return apology("Quantity cannot be less than zero")
        cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
        cash = cash[0]['cash']
        cost = quote['price'] * int(request.form.get("shares"))

        if cash < cost:
            return apology("Not enough funds", 403)

        db.execute("INSERT INTO Transactions (userid, stocksymbol, price, quantity, stockprice) VALUES (:userid, :stocksymbol, :price, :quantity, :stockprice)",
                    userid=session["user_id"], stocksymbol=request.form.get("symbol"), price=cost, quantity=request.form.get("shares"), stockprice=quote['price'])
        db.execute("UPDATE users SET cash = cash - :cost WHERE id = :userid", cost=cost, userid=session["user_id"])

        return redirect("/")


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    return jsonify("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = db.execute("SELECT stocksymbol, stockprice, date, time, quantity FROM Transactions WHERE userid = :userid", userid=session["user_id"])
    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/quote")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Stock symbol doesn't exist", 400)
        elif quote in quotes:
            return apology("Stock has already been added")
        else:
            quotes.append(quote)
            return render_template("quotes.html", quotes=quotes)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("Missing username!", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must provide password", 400)

        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        if password != confirm_password:
            return apology("Passwords must match!")

        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username = request.form.get("username"), hash = generate_password_hash(password))
        if not result:
            return apology("Username has been taken!", 400)

        # Remember which user has logged in
        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        session["user_id"] = rows[0]["id"]


        return redirect("/quote")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute("SELECT stocksymbol, SUM(quantity), SUM(price) FROM Transactions WHERE userid = :userid GROUP BY stocksymbol", userid=session["user_id"])
    if request.method == "GET":
        return render_template("sell.html", stocks=stocks)
    else:
        if shares > stocks[int(request.form.get("symbol"))]['SUM(quantity)']:
            return apology("Not enough stocks to sell", 403)
        elif int(request.form.get("shares")) < 0:
            return apology("Invalid number of stocks to sell", 400)
        else:
            cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=session["user_id"])
            cash = cash[0]['cash']
            quote = lookup(stocks[int(request.form.get("symbol"))]['stocksymbol'])
            price = quote['price'] * int(request.form.get("shares"))
            new_cash = cash + quote['price'] * int(request.form.get("shares"))
            db.execute("UPDATE users SET cash = :new_cash WHERE id = :userid", new_cash=new_cash, userid=session["user_id"])
            db.execute("INSERT INTO Transactions (userid, stocksymbol, price, quantity, stockprice) VALUES (:userid, :stocksymbol, :price, :quantity, :stockprice)",
                    userid=session["user_id"], stocksymbol=stocks[int(request.form.get("symbol"))]['stocksymbol'], price=price * -1, quantity=int(request.form.get("shares")) * -1, stockprice=quote['price'])
            stocks = db.execute("SELECT stocksymbol, SUM(quantity), SUM(price) FROM Transactions WHERE userid = :userid GROUP BY stocksymbol", userid=session["user_id"])
            if stocks[int(request.form.get("symbol"))]['SUM(quantity)'] == 0:
                db.execute("DELETE FROM Transactions WHERE stocksymbol=:stocksymbol AND userid=:userid", stocksymbol=stocks[int(request.form.get("symbol"))]['stocksymbol'], userid=session["user_id"])
            return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
