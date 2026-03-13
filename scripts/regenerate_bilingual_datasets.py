import json
from pathlib import Path

root = Path("datasets")

# ---------------- extraction ----------------
zh_cities = ["北京", "上海", "深圳", "杭州", "成都"]
zh_jobs = ["程序员", "摄影师", "设计师", "教师", "产品经理"]
zh_allergies = ["海鲜", "花生", "芒果", "虾", "牛奶"]
zh_hobbies = ["跑步", "游泳", "羽毛球", "徒步", "阅读"]

en_cities = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "Chengdu"]
en_jobs = ["software engineer", "photographer", "designer", "teacher", "product manager"]
en_allergies = ["seafood", "peanut", "mango", "shrimp", "milk"]
en_hobbies = ["running", "swimming", "badminton", "hiking", "reading"]

extraction = []
for i in range(1, 31):
    tid = f"ext_{i:03d}"
    if i <= 15:
        idx = i % 5
        city, job, allergy, hobby = zh_cities[idx], zh_jobs[idx], zh_allergies[idx], zh_hobbies[idx]
        extraction.append({
            "test_id": tid,
            "type": "extraction",
            "description": f"中文提取用例_{tid}",
            "turns": [
                {"role": "user", "content": f"我现在住在{city}，是一名{job}。平时喜欢{hobby}，另外我对{allergy}过敏。"},
                {"role": "user", "content": "今天有点忙，不过请记住这些信息。"},
            ],
            "expected_memory_contains": [city, job, allergy],
            "require_all": False,
        })
    else:
        idx = (i - 15) % 5
        city, job, allergy, hobby = en_cities[idx], en_jobs[idx], en_allergies[idx], en_hobbies[idx]
        extraction.append({
            "test_id": tid,
            "type": "extraction",
            "description": f"English extraction case_{tid}",
            "turns": [
                {"role": "user", "content": f"I live in {city} and work as a {job}. I like {hobby} and I am allergic to {allergy}."},
                {"role": "user", "content": "Please remember these details for later questions."},
            ],
            "expected_memory_contains": [city, job, allergy],
            "require_all": False,
        })

# ---------------- retrieval ----------------
zh_pet_names = ["旺财", "雪球", "布丁", "豆包", "奶糖"]
zh_pet_types = ["柯基", "布偶猫", "金毛", "鹦鹉", "兔子"]
zh_langs = ["英语", "日语", "法语", "西班牙语", "德语"]

en_pet_names = ["Wangcai", "Snowball", "Pudding", "Doubou", "Naitang"]
en_pet_types = ["corgi", "ragdoll cat", "golden retriever", "parrot", "rabbit"]
en_langs = ["English", "Japanese", "French", "Spanish", "German"]

retrieval = []
for i in range(1, 31):
    tid = f"ret_{i:03d}"
    if i <= 15:
        idx = i % 5
        pet_name, pet_type, city, lang = zh_pet_names[idx], zh_pet_types[idx], zh_cities[idx], zh_langs[idx]
        retrieval.append({
            "test_id": tid,
            "type": "retrieval",
            "description": f"中文检索用例_{tid}",
            "setup": [
                {"role": "user", "content": f"我养了一只叫{pet_name}的{pet_type}，现在住在{city}。"},
                {"role": "user", "content": f"我最近在学习{lang}，每天练习30分钟。"},
                {"role": "user", "content": "最近新闻很多，我们聊点别的。"},
            ],
            "query": "请告诉我我宠物的名字和我住的城市。",
            "expected_response_contains": [pet_name, city],
            "require_all": False,
        })
    else:
        idx = (i - 15) % 5
        pet_name, pet_type, city, lang = en_pet_names[idx], en_pet_types[idx], en_cities[idx], en_langs[idx]
        retrieval.append({
            "test_id": tid,
            "type": "retrieval",
            "description": f"English retrieval case_{tid}",
            "setup": [
                {"role": "user", "content": f"I have a {pet_type} named {pet_name}, and I live in {city}."},
                {"role": "user", "content": f"I am learning {lang} and practice 30 minutes per day."},
                {"role": "user", "content": "There is a lot of unrelated news today."},
            ],
            "query": "Tell me my pet name and the city where I live.",
            "expected_response_contains": [pet_name, city],
            "require_all": False,
        })

# ---------------- update ----------------
zh_old_jobs = ["程序员", "产品经理", "运营", "教师", "记者"]
zh_new_jobs = ["摄影师", "设计师", "咨询顾问", "自由译者", "数据科学家"]
zh_old_cities = ["广州", "厦门", "天津", "宁波", "福州"]
zh_new_cities = ["北京", "上海", "深圳", "杭州", "成都"]

en_old_jobs = ["programmer", "product manager", "operations", "teacher", "reporter"]
en_new_jobs = ["photographer", "designer", "consultant", "translator", "data scientist"]
en_old_cities = ["Guangzhou", "Xiamen", "Tianjin", "Ningbo", "Fuzhou"]
en_new_cities = ["Beijing", "Shanghai", "Shenzhen", "Hangzhou", "Chengdu"]

update = []
for i in range(1, 31):
    tid = f"upd_{i:03d}"
    if i <= 15:
        idx = i % 5
        old_job, new_job = zh_old_jobs[idx], zh_new_jobs[idx]
        old_city, new_city = zh_old_cities[idx], zh_new_cities[idx]
        update.append({
            "test_id": tid,
            "type": "update",
            "description": f"中文更新用例_{tid}",
            "turns": [
                {"role": "user", "content": f"我之前在{old_city}做{old_job}。"},
                {"role": "user", "content": f"最近我搬到了{new_city}，并转行做{new_job}。"},
            ],
            "query": "我现在在哪个城市、做什么工作？",
            "expected_response_contains": [new_city, new_job],
            "expected_memory_excludes": [old_city, old_job],
            "require_all_contains": False,
            "require_all_excludes": True,
        })
    else:
        idx = (i - 15) % 5
        old_job, new_job = en_old_jobs[idx], en_new_jobs[idx]
        old_city, new_city = en_old_cities[idx], en_new_cities[idx]
        update.append({
            "test_id": tid,
            "type": "update",
            "description": f"English update case_{tid}",
            "turns": [
                {"role": "user", "content": f"I previously worked as a {old_job} in {old_city}."},
                {"role": "user", "content": f"Recently I moved to {new_city} and changed my job to {new_job}."},
            ],
            "query": "Which city am I in now and what is my current job?",
            "expected_response_contains": [new_city, new_job],
            "expected_memory_excludes": [old_city, old_job],
            "require_all_contains": False,
            "require_all_excludes": True,
        })

(root / "extraction_tests.json").write_text(json.dumps(extraction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(root / "retrieval_tests.json").write_text(json.dumps(retrieval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(root / "update_tests.json").write_text(json.dumps(update, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("extraction", len(extraction), extraction[0]["description"], extraction[15]["description"])
print("retrieval", len(retrieval), retrieval[0]["description"], retrieval[15]["description"])
print("update", len(update), update[0]["description"], update[15]["description"])
