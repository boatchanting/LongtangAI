from flask import Flask, render_template, request, session, Response
import requests
import json
import os
from flask_session import Session

app = Flask(__name__)

# 配置 Flask 的 session
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# 预设提示词
PRESET_PROMPT = """"""


# 将对话历史保存到 JSON 文件
def save_to_json(user_input, model_output):
    dialog_history = {
        "user_input": user_input,
        "model_output": model_output
    }
    
    # 如果文件不存在，创建一个空的对话记录
    if not os.path.exists('dialog_history.json'):
        with open('dialog_history.json', 'w') as f:
            json.dump([], f)
    
    # 读取现有的对话记录
    with open('dialog_history.json', 'r') as f:
        history = json.load(f)
    
    # 添加新对话
    history.append(dialog_history)
    
    # 将更新后的历史记录写回文件
    with open('dialog_history.json', 'w') as f:
        json.dump(history, f, indent=4)

# 从 JSON 文件中读取对话历史
def load_from_json():
    if os.path.exists('dialog_history.json'):
        with open('dialog_history.json', 'r') as f:
            history = json.load(f)
            return history
    return []  # 如果文件不存在，返回空列表

# SSE 用于流式传输模型响应
def generate_response_stream(prompt, context_tokens=None):
    url = "http://127.0.0.1:11434/api/generate"  # Ollama API的URL
    data = {
        "model": "qwen2.5",
        "prompt": prompt
    }
    
    if context_tokens:
        data["context"] = context_tokens

    response = requests.post(url, json=data, stream=True)
    
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            try:
                json_data = json.loads(decoded_line)
                yield f"data: {json_data['response']}\n\n"  # SSE 格式
                if json_data.get('done'):
                    break
            except json.JSONDecodeError:
                print(f"Failed to decode JSON: {decoded_line}")
                yield f"data: Error processing response\n\n"

# SSE 路由：提供流式响应
@app.route('/stream', methods=['POST'])
def stream_response():
    user_input = request.form['question']
    dialog_history = session.get('dialog_history', load_from_json())  # 从JSON文件加载历史记录
    context_tokens = session.get('context_tokens', None)

    # 将用户输入添加到对话历史
    dialog_history.append(f"You: {user_input}")
    
    # 在用户输入之前加入预设的提示词
    combined_prompt = PRESET_PROMPT + "\n" + "\n".join(dialog_history)

    return Response(generate_response_stream(combined_prompt, context_tokens), content_type='text/event-stream')

# Flask 路由：主页，显示用户输入表单
@app.route('/')
def index():
    return render_template('my_ai.html')

# 处理重置对话的路由
@app.route('/reset', methods=['POST'])
def reset():
    session.pop('dialog_history', None)
    session.pop('context_tokens', None)
    
    # 清空 JSON 文件
    with open('dialog_history.json', 'w') as f:
        json.dump([], f)
    
    return render_template('my_ai.html')

if __name__ == '__main__':
    app.run(debug=True)
