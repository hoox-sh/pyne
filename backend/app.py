from flask import Flask, request, jsonify
from flask_cors import CORS
# import pynescript.ast.helper as pine

app = Flask(__name__)
CORS(app)


@app.route("/run", methods=["POST"])
def run_pine_script():
    data = request.get_json()
    pine_script = data.get("script", "")

    # Here you would use pynescript to parse and process the script
    # For now, we'll just return a dummy response.
    # try:
    #     ast = pine.parse(pine_script)
    #     # In a real scenario, you would evaluate the AST
    #     # and return meaningful data.
    #     response_data = {"status": "success", "message": "Script parsed successfully", "ast": str(ast)}
    # except Exception as e:
    #     response_data = {"status": "error", "message": str(e)}

    # Dummy response
    response_data = {"status": "success", "message": "Pine script received", "data": [1, 2, 3, 4, 5]}

    return jsonify(response_data)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
