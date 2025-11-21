from flask import Flask, request, jsonify, render_template_string
import pymysql
from flask_cors import CORS
from dotenv import load_dotenv
import os
import base64

# ----------------------------------------
# ENV LOAD
# ----------------------------------------
load_dotenv()

# Flask에서 /img 폴더를 static 폴더로 사용
app = Flask(__name__, static_folder="img")
CORS(app)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "cursorclass": pymysql.cursors.DictCursor
}

# ----------------------------------------
# bytes → JSON safe 변환
# ----------------------------------------
def make_json_safe(row):
    safe = {}
    for k, v in row.items():
        if isinstance(v, bytes):
            try:
                safe[k] = v.decode("utf-8")
            except:
                safe[k] = base64.b64encode(v).decode("utf-8")
        else:
            safe[k] = v
    return safe

# ----------------------------------------
# DB QUERY
# ----------------------------------------
def query_db(sql, params=None):
    conn = pymysql.connect(**DB_CONFIG)
    with conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [make_json_safe(r) for r in rows]

# ----------------------------------------
# HTML TEMPLATE (짱구 60% 우측 하단 fixed + 로딩 UI)
# ----------------------------------------

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>HIPARKING DMS 조회 툴</title>

<style>
body {
    font-family: Arial, Pretendard, sans-serif;
    margin: 0;
    background: #ffffff;
}

.floating-jjanggu {
    position: fixed;
    right: 20px;
    bottom: 20px;
    width: 800px;
    z-index: 9999;
    pointer-events: none;
    opacity: 0.95;
}

.header {
    background-color: #FF6A00;
    color: white;
    padding: 40px 30px;
    font-size: 32px;
    font-weight: 700;
}

.sub {
    margin-top: -20px;
    padding-left: 32px;
    color: #ffffff;
    opacity: 0.9;
    font-size: 16px;
}

.container {
    padding: 30px;
    background: rgba(255,255,255,0.92);
    margin: 20px;
    border-radius: 12px;
}

label {
    font-size: 18px;
    font-weight: 600;
}

input {
    padding: 10px;
    width: 400px;
    border-radius: 6px;
    border: 1px solid #ccc;
    margin-top: 8px;
    font-size: 16px;
}

button {
    padding: 10px 20px;
    background: #FF6A00;
    border: none;
    border-radius: 6px;
    color: white;
    font-size: 16px;
    font-weight: 600;
    margin-left: 10px;
    cursor: pointer;
}

button:hover {
    background: #e85f00;
}

#loading {
    display: none;
    font-size: 18px;
    font-weight: 600;
    margin-top: 20px;
}

.table-block {
    margin-top: 40px;
}

.table-title {
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 12px;
    color: #333;
}

table {
    border-collapse: collapse;
    width: 100%;
    font-size: 14px;
}

th, td {
    padding: 10px;
    border: 1px solid #ddd;
}

th {
    background: #f5f5f5;
    font-weight: 700;
}

.empty {
    color: #888;
    font-style: italic;
}
</style>

</head>
<body>

<!-- 짱구 이미지 오른쪽 아래 고정 -->
<img src="/img/main.png" class="floating-jjanggu">

<div class="header">HIPARKING DMS 조회</div>
<div class="sub">YG family</div>

<div class="container">
    <label>TicketID 또는 주문서 번호(OrderSheetID)를 입력하세요</label><br>
    <input type="text" id="searchKey" placeholder="예: 0K329020251113000032 또는 0000320H251120000072">
    <button onclick="search()">조회</button>

    <div id="loading">🔄 로딩중입니다...</div>

    <div id="results"></div>
</div>

<script>
function toTable(name, rows) {
    if (!rows || rows.length === 0) {
        return `<div class='table-block'>
                    <div class='table-title'>${name}</div>
                    <div class='empty'>데이터 없음</div>
                </div>`;
    }

    let keys = Object.keys(rows[0]);

    let header = keys.map(k => `<th>${k}</th>`).join("");
    let body = rows.map(r => {
        let row = keys.map(k => `<td>${r[k] ?? ""}</td>`).join("");
        return `<tr>${row}</tr>`;
    }).join("");

    return `
        <div class='table-block'>
            <div class='table-title'>${name} (${rows.length}건)</div>
            <table>
                <thead><tr>${header}</tr></thead>
                <tbody>${body}</tbody>
            </table>
        </div>
    `;
}

function search() {
    const key = document.getElementById("searchKey").value;
    if (!key) {
        alert("입력하세요.");
        return;
    }

    document.getElementById("loading").style.display = "block";
    document.getElementById("results").innerHTML = "";

    fetch(`/order-info?key=${key}`)
      .then(res => res.json())
      .then(data => {
        const html =
            toTable("vtb_dms_order", data.vtb_dms_order) +
            toTable("vtb_dms_order_cancel", data.vtb_dms_order_cancel) +
            toTable("tb_trade", data.tb_trade);

        document.getElementById("results").innerHTML = html;
      })
      .catch(err => {
        document.getElementById("results").innerHTML =
            "<div class='empty'>오류 발생: " + err + "</div>";
      })
      .finally(() => {
        document.getElementById("loading").style.display = "none";
      });
}
</script>

</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

# ----------------------------------------
#   TicketID / OrderSheetID 자동 분기
# ----------------------------------------
@app.route("/order-info", methods=["GET"])
def get_order_info():
    key = request.args.get("key")

    if not key:
        return jsonify({"error": "key is required"}), 400

    try:
        # 1) TicketID 조회
        sql_ticket_check = """
            SELECT TicketID FROM vtb_dms_order
            WHERE TicketID = %s LIMIT 1;
        """
        ticket_rows = query_db(sql_ticket_check, (key,))

        if ticket_rows:
            sql1 = """SELECT * FROM vtb_dms_order
                      WHERE TicketID = %s ORDER BY ApprovalType DESC;"""
            dms_order = query_db(sql1, (key,))

            sql2 = """SELECT * FROM vtb_dms_order_cancel
                      WHERE TicketID = %s;"""
            dms_cancel = query_db(sql2, (key,))

            sql3 = """SELECT * FROM tb_trade
                      WHERE shop_order_no = %s;"""
            trade = query_db(sql3, (key,))

            return jsonify({
                "mode": "TICKET",
                "search_key": key,
                "vtb_dms_order": dms_order,
                "vtb_dms_order_cancel": dms_cancel,
                "tb_trade": trade
            })

        # 2) OrderSheetID 조회
        sql_order_check = """
            SELECT OrderSheetID FROM vtb_dms_order
            WHERE OrderSheetID = %s LIMIT 1;
        """
        order_rows = query_db(sql_order_check, (key,))

        if order_rows:
            sql1 = """SELECT * FROM vtb_dms_order
                      WHERE OrderSheetID = %s ORDER BY ApprovalType DESC;"""
            dms_order = query_db(sql1, (key,))

            sql2 = """
                SELECT * FROM vtb_dms_order_cancel
                WHERE TicketID IN (
                    SELECT TicketID FROM vtb_dms_order
                    WHERE OrderSheetID = %s
                );
            """
            dms_cancel = query_db(sql2, (key,))

            sql3 = """SELECT * FROM tb_trade
                      WHERE shop_order_no = %s;"""
            trade = query_db(sql3, (key,))

            return jsonify({
                "mode": "ORDERSHEET",
                "search_key": key,
                "vtb_dms_order": dms_order,
                "vtb_dms_order_cancel": dms_cancel,
                "tb_trade": trade
            })

        return jsonify({
            "status": "not_found",
            "search_key": key,
            "vtb_dms_order": [],
            "vtb_dms_order_cancel": [],
            "tb_trade": []
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ----------------------------------------
# RUN
# ----------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5011, debug=True)

