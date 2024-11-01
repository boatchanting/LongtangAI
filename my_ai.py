from flask import Flask, render_template, request, session, Response
import jieba
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

# 加载自定义字典
jieba.load_userdict('custom_dict.txt')

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

    # 查找知识库中的相关信息
    kb_information = search_knowledge_base(user_input)
    
    # 构建最终的提示词
    if kb_information:
        PRESET_PROMPT_WITH_KB = f"{PRESET_PROMPT}\nKnowledge Base Information:\n{kb_information}\n"
    else:
        PRESET_PROMPT_WITH_KB = PRESET_PROMPT

    # 调试用：打印知识库的搜索结果
    if kb_information:
        print(f"Knowledge Base Information: {kb_information}")
    else:
        print("No knowledge base information found.")

    # 将用户输入添加到对话历史
    dialog_history.append(f"You: {user_input}")
    
    # 在用户输入之前加入预设的提示词（包括可能的知识库信息）
    combined_prompt = PRESET_PROMPT_WITH_KB + "\n" + "\n".join(dialog_history)

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

def search_knowledge_base(query):
    """从知识库中搜索与查询相关的信息"""
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    knowledge_base_path = os.path.join(current_script_path, 'knowledge_base.json')

    # 读取知识库文件
    with open(knowledge_base_path, 'r', encoding='utf-8') as file:
        knowledge_base = json.load(file)
    
    # 使用 jieba 对查询进行分词
    query_words = set(jieba.lcut(query))

    print(f"User input words: {query_words}")
    
    # 搜索与查询匹配的知识库条目
    for entry in knowledge_base:
        # 检查知识库条目的 id 是否在查询单词中
        if entry['id'] in query_words:
            return entry['information']
    
    return None  # 如果没有找到匹配项，返回None
# 测试用代码
"""
query = "我想询问有关东方明珠的故事"
result = search_knowledge_base(query)
print(result)
"""
if __name__ == '__main__':
    app.run(debug=True)



