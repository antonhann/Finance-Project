import os


from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from time import ctime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
#e145746a3bbd4a129bf3ff5c21669a36
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():

    cash = db.execute("SELECT cash from users where id = ?", session["user_id"])
    cash = cash[0]['cash']
    col1 = ['symbol', 'stock_name']
    col2 = ['price', 'total']
    portfolio = db.execute("SELECT * from portfolio where user_id = ?", session["user_id"])
    cost = db.execute("SELECT sum(total) from portfolio where user_id = ?", session["user_id"])
    total = cash - cost[0]['sum(total)']
    real = total + cost[0]['sum(total)']
    return(render_template("index.html", portfolio = portfolio, cash = cash, col1 = col1, col2 = col2, real = real, total = total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("symbol required", request.form.get("symbol"))

        symbol = request.form.get("symbol")
        fshares = request.form.get("shares")
        try:
            shares = int(fshares)
        except ValueError:
            return apology("only full integer shares", 400)
        if shares < 1:
            return apology("only full shares", 400)

        search = lookup(symbol)

        if search == None:
            return apology("symbol DNE", 400)
        name = search["name"]
        price = search["price"]
        ticker = search["symbol"]
        time = ctime()
        cost = price * shares
        cash = db.execute("SELECT cash from users where id = ?", session["user_id"])


        if cost > cash[0]["cash"]:
            return apology("you too broke", 400)

        #check if stock inside portfolio
        check = db.execute("Select stock_name from portfolio where user_id = ? and stock_name = ?", session['user_id'], name)
        if len(check) == 0:
            db.execute("INSERT INTO portfolio (user_id,symbol,stock_name,shares,price,total) VALUES(?,?,?,?,?,?)", session["user_id"], ticker, name, shares, price, cost)
            db.execute("update users set cash = ? where id = ?", cash[0]["cash"]-cost, session['user_id'], )
        else:
            currentprice = db.execute("Select price from portfolio where user_id = ? and stock_name = ?", session['user_id'], name)
            currentshares = db.execute("Select shares from portfolio where user_id = ? and stock_name = ?", session['user_id'], name)
            newshares = shares + currentshares[0]["shares"]
            db.execute("update portfolio set shares = ? where user_id = ? and stock_name = ?", newshares, session['user_id'], name)
            newprice = ((currentprice[0]['price']*currentshares[0]["shares"]) + (price*shares)) / (currentshares[0]["shares"]+shares)
            newtotal = newprice * newshares
            db.execute("update portfolio set price = ? where user_id = ? and stock_name = ?", newprice, session['user_id'], name)
            db.execute("update portfolio set total = ? where user_id = ? and stock_name = ?", newtotal, session['user_id'], name)
            db.execute("update users set cash = ? where id = ?", cash[0]["cash"]-cost, session['user_id'], )
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES(?,?,?,?,?)", session['user_id'], symbol, shares, price, time)

        return redirect('/')


    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    col1 = ['shares', 'price', 'time']
    transactions = db.execute("SELECT * from transactions where user_id = ?", session["user_id"])
    return(render_template("history.html", transactions = transactions, col1 = col1))


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

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
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("symbol required", 400)

        symbol = request.form.get("symbol")
        search = lookup(symbol)

        if search is None:
            return apology("symbol DNE", 400)
        else:
            name = search["name"]
            price = search["price"]
            ticker = search["symbol"]
            return render_template("quoted.html", name=name, price=price, ticker=ticker)

    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) == 1:
            return apology("username is already taken", 400)
        if password != confirmation:
            return apology("password confirmation is wrong", 400)
        none = 'none'
        passwordhash = generate_password_hash(password)
        db.execute("INSERT into users (username, hash) VALUES(?,?)", username, passwordhash)
        id = db.execute("select id from users where username = ?", username)
        db.execute("INSERT into portfolio(user_id, symbol, stock_name, shares, price, total) VALUES (?,?,?,?,?,?)", id[0]["id"], 'NULL', 'NULL', 0, 0, 0)
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("symbol required", request.form.get("symbol"))

        fshares = request.form.get("shares")
        try:
            shares = int(fshares)
        except ValueError:
            return apology("only full integer shares", 400)
        if shares < 1:
            return apology("only full shares", 400)

        symbol = request.form.get("symbol")
        search = lookup(symbol)

        if search == None:
            return apology("symbol DNE", 400)
        name = search["name"]
        currentprice = db.execute("Select price from portfolio where user_id = ? and stock_name = ?", session['user_id'], name)
        time = ctime()
        gain = currentprice[0]['price'] * shares
        cshares = db.execute("SELECT shares from portfolio where user_id = ? and stock_name = ?", session["user_id"], name)
        cash = db.execute("SELECT cash from users where id = ?", session["user_id"])

        #check if stock inside portfolio
        check = db.execute("Select stock_name from portfolio where user_id = ? and stock_name = ?", session['user_id'], name)
        if len(check) == 0:
            return apology("you dont own this stock", 400)
        else:
            if shares > cshares[0]['shares']:
                return apology("you dont own that many", 400)
            else:
                currentprice = db.execute("Select price from portfolio where user_id = ? and stock_name = ?", session['user_id'], name)
                print(cash[0]['cash'])
                newshares = cshares[0]["shares"] - shares
                db.execute("update portfolio set shares = ? where user_id = ? and stock_name = ?", newshares, session['user_id'], name)
                newtotal = newshares * currentprice[0]['price']
                if newshares == 0:
                     db.execute("update users set cash = ? where id = ?", cash[0]["cash"] + gain, session['user_id'], )
                     db.execute("Delete from portfolio where user_id = ? and stock_name = ?", session['user_id'], name)
                else:
                    db.execute("update portfolio set total = ? where user_id = ? and stock_name = ?", newtotal, session['user_id'], name)
                    db.execute("update users set cash = ? where id = ?", cash[0]["cash"] + gain, session['user_id'], )
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES(?,?,?,?,?)", session['user_id'], symbol, -(shares), currentprice[0]['price'], time)

        return redirect('/')

    current = db.execute('select shares from portfolio where user_id = ?', session['user_id'])
    return render_template("sell.html", current = current)