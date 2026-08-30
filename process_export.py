#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apple Health Export Processor & Secure Dashboard Builder
=========================================================
Apple Health のエクスポートデータ（export.zip または export.xml）を高速ストリーミング解析し、
集計結果を AES-256-GCM で暗号化して index.html のダッシュボードを生成・更新します。
"""

import os
import sys
import re
import json
import zipfile
import argparse
import datetime
from collections import defaultdict
import xml.etree.ElementTree as ET

# 暗号化ライブラリの確認
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except ImportError:
    print("[ERROR] 'cryptography' ライブラリがインストールされていません。")
    print("以下のコマンドでインストールしてください:")
    print("   pip install cryptography")
    sys.exit(1)


# ワークアウト種別マッピング（Apple Health Type -> 日本語名）
WORKOUT_TYPE_MAP = {
    "HKWorkoutActivityTypeWalking": "ウォーキング",
    "HKWorkoutActivityTypeRunning": "ランニング",
    "HKWorkoutActivityTypeCycling": "サイクリング",
    "HKWorkoutActivityTypeSwimming": "スイミング",
    "HKWorkoutActivityTypeHiking": "ハイキング",
    "HKWorkoutActivityTypeYoga": "ヨガ",
    "HKWorkoutActivityTypeFunctionalStrengthTraining": "筋力トレーニング",
    "HKWorkoutActivityTypeTraditionalStrengthTraining": "筋力トレーニング",
    "HKWorkoutActivityTypeCoreTraining": "コアトレーニング",
    "HKWorkoutActivityTypeElliptical": "エリプティカル",
    "HKWorkoutActivityTypeRower": "ローイング",
    "HKWorkoutActivityTypeStairClimbing": "ステアクライミング",
    "HKWorkoutActivityTypeHighIntensityIntervalTraining": "HIIT",
    "HKWorkoutActivityTypePilates": "ピラティス",
    "HKWorkoutActivityTypeDance": "ダンス",
    "HKWorkoutActivityTypeKickboxing": "キックボクシング",
    "HKWorkoutActivityTypeCooldown": "クールダウン",
    "HKWorkoutActivityTypeFlexibility": "ストレッチ",
    "HKWorkoutActivityTypeCrossTraining": "クロストレーニング",
    "HKWorkoutActivityTypeCardio": "有酸素運動",
}


def parse_date(date_str):
    """'2026-08-28 15:30:00 +0900' 形式の日付文字列をパース"""
    if not date_str:
        return None
    try:
        date_part = date_str[:10]
        return date_part
    except Exception:
        return None


def parse_datetime(date_str):
    """日付時刻のパース"""
    if not date_str:
        return None
    try:
        clean_str = date_str[:19]
        return datetime.datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def get_xml_stream(input_path):
    """ZIP または XML ファイルからストリームを取得"""
    if input_path.endswith(".zip"):
        print(f"[INFO] ZIPファイルを展開中: {input_path}")
        z = zipfile.ZipFile(input_path, 'r')
        xml_filename = None
        for name in z.namelist():
            if name.endswith("export.xml"):
                xml_filename = name
                break
        if not xml_filename:
            raise FileNotFoundError("ZIPファイル内に export.xml が見つかりませんでした。")
        print(f"[INFO] XMLエントリを検出: {xml_filename}")
        return z.open(xml_filename), z
    elif input_path.endswith(".xml"):
        print(f"[INFO] XMLファイルを読み込み中: {input_path}")
        return open(input_path, "rb"), None
    else:
        raise ValueError("入力ファイルは .zip または .xml である必要があります。")


def process_health_data(file_stream):
    """
    ストリーミングXMLパーサーでメモリを消費せずに大規模データを解析・集計
    """
    print("[INFO] ヘルスケアデータをストリーミング集計中...")

    daily_steps = defaultdict(float)
    daily_distance = defaultdict(float)
    daily_active_cal = defaultdict(float)
    daily_basal_cal = defaultdict(float)
    daily_resting_hr = defaultdict(list)
    daily_hrv = defaultdict(list)
    daily_vo2max = defaultdict(list)
    daily_spo2 = defaultdict(list)
    daily_walking_asym = defaultdict(list)

    daily_sleep_total = defaultdict(float)
    daily_sleep_deep = defaultdict(float)
    daily_sleep_core = defaultdict(float)
    daily_sleep_rem = defaultdict(float)
    daily_sleep_awake = defaultdict(float)

    workouts_list = []

    context = ET.iterparse(file_stream, events=("end",))
    count = 0

    for event, elem in context:
        tag = elem.tag

        if tag == "Record":
            count += 1
            if count % 500000 == 0:
                print(f"   ... {count:,} 件のレコードを処理完了")

            record_type = elem.attrib.get("type", "")
            start_date_str = elem.attrib.get("startDate", "")
            val_str = elem.attrib.get("value", "")

            date_key = parse_date(start_date_str)
            if not date_key:
                elem.clear()
                continue

            try:
                val = float(val_str) if val_str else 0.0
            except ValueError:
                val = 0.0

            if record_type == "HKQuantityTypeIdentifierStepCount":
                daily_steps[date_key] += val
            elif record_type == "HKQuantityTypeIdentifierDistanceWalkingRunning":
                daily_distance[date_key] += val
            elif record_type == "HKQuantityTypeIdentifierActiveEnergyBurned":
                daily_active_cal[date_key] += val
            elif record_type == "HKQuantityTypeIdentifierBasalEnergyBurned":
                daily_basal_cal[date_key] += val
            elif record_type == "HKQuantityTypeIdentifierRestingHeartRate":
                if val > 0: daily_resting_hr[date_key].append(val)
            elif record_type == "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
                if val > 0: daily_hrv[date_key].append(val)
            elif record_type == "HKQuantityTypeIdentifierVO2Max":
                if val > 0: daily_vo2max[date_key].append(val)
            elif record_type == "HKQuantityTypeIdentifierOxygenSaturation":
                spo2_pct = val * 100.0 if val <= 1.0 else val
                if spo2_pct > 0: daily_spo2[date_key].append(spo2_pct)
            elif record_type == "HKQuantityTypeIdentifierWalkingAsymmetryPercentage":
                asym_pct = val * 100.0 if val <= 1.0 else val
                daily_walking_asym[date_key].append(asym_pct)
            elif record_type == "HKCategoryTypeIdentifierSleepAnalysis":
                start_dt = parse_datetime(start_date_str)
                end_dt = parse_datetime(elem.attrib.get("endDate", ""))
                if start_dt and end_dt:
                    duration_sec = (end_dt - start_dt).total_seconds()
                    val_s = str(elem.attrib.get("value", ""))
                    if "AsleepDeep" in val_s or val_s == "4":
                        daily_sleep_deep[date_key] += duration_sec
                        daily_sleep_total[date_key] += duration_sec
                    elif "AsleepCore" in val_s or val_s == "3":
                        daily_sleep_core[date_key] += duration_sec
                        daily_sleep_total[date_key] += duration_sec
                    elif "AsleepREM" in val_s or val_s == "5":
                        daily_sleep_rem[date_key] += duration_sec
                        daily_sleep_total[date_key] += duration_sec
                    elif "Asleep" in val_s or val_s == "1" or val_s == "HKCategoryValueSleepAnalysisAsleep":
                        daily_sleep_total[date_key] += duration_sec
                    elif "Awake" in val_s or val_s == "2":
                        daily_sleep_awake[date_key] += duration_sec

            elem.clear()

        elif tag == "Workout":
            w_type = elem.attrib.get("workoutActivityType", "")
            sport_name = WORKOUT_TYPE_MAP.get(w_type, w_type.replace("HKWorkoutActivityType", ""))
            start_date_str = elem.attrib.get("startDate", "")
            duration_str = elem.attrib.get("duration", "0")
            dist_str = elem.attrib.get("totalDistance", "0")
            cal_str = elem.attrib.get("totalEnergyBurned", "0")

            date_key = parse_date(start_date_str)
            try:
                duration_min = round(float(duration_str) / 60.0, 1) if float(duration_str) > 300 else round(float(duration_str), 1)
            except Exception:
                duration_min = 0.0

            try:
                dist_km = round(float(dist_str), 2)
            except Exception:
                dist_km = 0.0

            try:
                cal_kcal = round(float(cal_str), 1)
            except Exception:
                cal_kcal = 0.0

            workouts_list.append({
                "日付": date_key or "",
                "ワークアウト種目": sport_name,
                "運動時間 (分)": duration_min,
                "距離 (km)": dist_km,
                "消費カロリー (kcal)": cal_kcal,
                "平均心拍数 (bpm)": None
            })
            elem.clear()

    print(f"[INFO] 全レコード集計完了: 合計 {count:,} 件")

    all_dates = sorted(set(list(daily_steps.keys()) + list(daily_distance.keys()) + list(daily_active_cal.keys())))
    if not all_dates:
        raise ValueError("ヘルスケアレコードが見つかりませんでした。")

    start_date = all_dates[0]
    end_date = all_dates[-1]

    months = defaultdict(lambda: {
        "days": set(), "steps": 0.0, "max_step": 0.0, "dist": 0.0, "active_cal": 0.0, "basal_cal": 0.0,
        "resting_hr": [], "hrv": [], "vo2max": [], "spo2": [], "walking_asym": [],
        "sleep_hours": [], "sleep_deep_hours": [], "sleep_core_hours": [], "sleep_rem_hours": [],
        "workout_count": 0, "workout_duration": 0.0, "workout_cal": 0.0
    })

    for d in all_dates:
        m = d[:7]
        st = daily_steps[d]
        months[m]["days"].add(d)
        months[m]["steps"] += st
        if st > months[m]["max_step"]:
            months[m]["max_step"] = st
        months[m]["dist"] += daily_distance[d]
        months[m]["active_cal"] += daily_active_cal[d]
        months[m]["basal_cal"] += daily_basal_cal[d]

        if daily_resting_hr[d]: months[m]["resting_hr"].extend(daily_resting_hr[d])
        if daily_hrv[d]: months[m]["hrv"].extend(daily_hrv[d])
        if daily_vo2max[d]: months[m]["vo2max"].extend(daily_vo2max[d])
        if daily_spo2[d]: months[m]["spo2"].extend(daily_spo2[d])
        if daily_walking_asym[d]: months[m]["walking_asym"].extend(daily_walking_asym[d])

        if daily_sleep_total[d] > 0:
            months[m]["sleep_hours"].append(daily_sleep_total[d] / 3600.0)
        if daily_sleep_deep[d] > 0:
            months[m]["sleep_deep_hours"].append(daily_sleep_deep[d] / 3600.0)
        if daily_sleep_core[d] > 0:
            months[m]["sleep_core_hours"].append(daily_sleep_core[d] / 3600.0)
        if daily_sleep_rem[d] > 0:
            months[m]["sleep_rem_hours"].append(daily_sleep_rem[d] / 3600.0)

    for w in workouts_list:
        if w["日付"]:
            m = w["日付"][:7]
            if m in months:
                months[m]["workout_count"] += 1
                months[m]["workout_duration"] += w["運動時間 (分)"]
                months[m]["workout_cal"] += w["消費カロリー (kcal)"]

    monthly_result = []
    for m in sorted(months.keys()):
        data = months[m]
        d_cnt = len(data["days"]) or 1
        total_cal = data["active_cal"] + data["basal_cal"]

        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else None

        monthly_result.append({
            "年月": m,
            "記録日数": d_cnt,
            "月間総歩数": int(data["steps"]),
            "1日平均歩数": round(data["steps"] / d_cnt, 1),
            "月間最大歩数": int(data["max_step"]),
            "月間総距離 (km)": round(data["dist"], 2),
            "1日平均距離 (km)": round(data["dist"] / d_cnt, 2),
            "月間アクティブカロリー (kcal)": round(data["active_cal"], 1),
            "1日平均アクティブカロリー (kcal)": round(data["active_cal"] / d_cnt, 1),
            "月間総消費カロリー (kcal)": round(total_cal, 1),
            "1日平均総消費カロリー (kcal)": round(total_cal / d_cnt, 1),
            "平均安静時心拍数 (bpm)": avg(data["resting_hr"]),
            "平均心拍変動 HRV (ms)": avg(data["hrv"]),
            "平均VO2Max": avg(data["vo2max"]),
            "平均血中酸素ウェルネス (%)": avg(data["spo2"]),
            "平均歩行非対称性 (%)": avg(data["walking_asym"]),
            "平均実睡眠時間 (時間)": avg(data["sleep_hours"]),
            "平均深い睡眠 (時間)": avg(data["sleep_deep_hours"]),
            "平均コア睡眠 (時間)": avg(data["sleep_core_hours"]),
            "平均レム睡眠 (時間)": avg(data["sleep_rem_hours"]),
            "月間ワークアウト回数": data["workout_count"],
            "月間ワークアウト総時間 (分)": round(data["workout_duration"], 1),
            "月間ワークアウト総カロリー (kcal)": round(data["workout_cal"], 1)
        })

    years = defaultdict(lambda: {
        "days": set(), "steps": 0.0, "max_step": 0.0, "dist": 0.0, "active_cal": 0.0, "basal_cal": 0.0,
        "resting_hr": [], "hrv": [], "vo2max": [], "spo2": [], "walking_asym": [],
        "sleep_hours": [], "workout_count": 0, "workout_duration": 0.0, "workout_cal": 0.0
    })

    for d in all_dates:
        y = int(d[:4])
        st = daily_steps[d]
        years[y]["days"].add(d)
        years[y]["steps"] += st
        if st > years[y]["max_step"]:
            years[y]["max_step"] = st
        years[y]["dist"] += daily_distance[d]
        years[y]["active_cal"] += daily_active_cal[d]
        years[y]["basal_cal"] += daily_basal_cal[d]

        if daily_resting_hr[d]: years[y]["resting_hr"].extend(daily_resting_hr[d])
        if daily_hrv[d]: years[y]["hrv"].extend(daily_hrv[d])
        if daily_vo2max[d]: years[y]["vo2max"].extend(daily_vo2max[d])
        if daily_spo2[d]: years[y]["spo2"].extend(daily_spo2[d])
        if daily_walking_asym[d]: years[y]["walking_asym"].extend(daily_walking_asym[d])
        if daily_sleep_total[d] > 0:
            years[y]["sleep_hours"].append(daily_sleep_total[d] / 3600.0)

    for w in workouts_list:
        if w["日付"]:
            try:
                y = int(w["日付"][:4])
                if y in years:
                    years[y]["workout_count"] += 1
                    years[y]["workout_duration"] += w["運動時間 (分)"]
                    years[y]["workout_cal"] += w["消費カロリー (kcal)"]
            except Exception:
                pass

    yearly_result = []
    for y in sorted(years.keys(), reverse=True):
        data = years[y]
        d_cnt = len(data["days"]) or 1
        total_cal = data["active_cal"] + data["basal_cal"]

        def avg(lst):
            return round(sum(lst) / len(lst), 1) if lst else None

        yearly_result.append({
            "年": y,
            "記録日数": d_cnt,
            "年間総歩数": int(data["steps"]),
            "1日平均歩数": round(data["steps"] / d_cnt, 1),
            "年間最大歩数": int(data["max_step"]),
            "年間総距離 (km)": round(data["dist"], 2),
            "1日平均距離 (km)": round(data["dist"] / d_cnt, 2),
            "年間アクティブカロリー (kcal)": round(data["active_cal"], 1),
            "1日平均アクティブカロリー (kcal)": round(data["active_cal"] / d_cnt, 1),
            "年間総消費カロリー (kcal)": round(total_cal, 1),
            "1日平均総消費カロリー (kcal)": round(total_cal / d_cnt, 1),
            "平均安静時心拍数 (bpm)": avg(data["resting_hr"]),
            "平均心拍変動 HRV (ms)": avg(data["hrv"]),
            "平均VO2Max": avg(data["vo2max"]),
            "平均血中酸素ウェルネス (%)": avg(data["spo2"]),
            "平均歩行非対称性 (%)": avg(data["walking_asym"]),
            "平均実睡眠時間 (時間)": avg(data["sleep_hours"]),
            "年間ワークアウト回数": data["workout_count"],
            "年間ワークアウト総時間 (分)": round(data["workout_duration"], 1),
            "年間ワークアウト総カロリー (kcal)": round(data["workout_cal"], 1)
        })

    weekday_names = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
    weekday_steps = defaultdict(list)
    weekday_cal = defaultdict(list)

    for d in all_dates:
        dt = datetime.datetime.strptime(d, "%Y-%m-%d")
        w_idx = dt.weekday()
        w_name = weekday_names[w_idx]
        weekday_steps[w_name].append(daily_steps[d])
        weekday_cal[w_name].append(daily_active_cal[d])

    weekday_result = []
    for w_name in weekday_names:
        s_list = weekday_steps[w_name]
        c_list = weekday_cal[w_name]
        weekday_result.append({
            "曜日": w_name,
            "歩数 (Steps)": round(sum(s_list) / len(s_list), 1) if s_list else 0,
            "アクティブ消費カロリー (kcal)": round(sum(c_list) / len(c_list), 1) if c_list else 0
        })

    w_sum = defaultdict(lambda: {"count": 0, "duration": 0.0, "dist": 0.0, "cal": 0.0})
    for w in workouts_list:
        s = w["ワークアウト種目"]
        w_sum[s]["count"] += 1
        w_sum[s]["duration"] += w["運動時間 (分)"]
        w_sum[s]["dist"] += w["距離 (km)"]
        w_sum[s]["cal"] += w["消費カロリー (kcal)"]

    workout_summary = []
    for s, v in sorted(w_sum.items(), key=lambda x: x[1]["count"], reverse=True):
        c = v["count"] or 1
        workout_summary.append({
            "種目名": s,
            "実施回数": v["count"],
            "総運動時間 (分)": round(v["duration"], 1),
            "平均運動時間 (分)": round(v["duration"] / c, 1),
            "総距離 (km)": round(v["dist"], 2),
            "平均距離 (km)": round(v["dist"] / c, 2),
            "総消費カロリー (kcal)": round(v["cal"], 1),
            "平均消費カロリー (kcal)": round(v["cal"] / c, 1),
            "平均心拍数 (bpm)": None
        })

    total_days = len(all_dates)
    total_steps = sum(daily_steps.values())
    total_dist = sum(daily_distance.values())
    total_active_cal = sum(daily_active_cal.values())
    total_all_cal = total_active_cal + sum(daily_basal_cal.values())

    all_rhr = [val for sub in daily_resting_hr.values() for val in sub]
    all_hrv = [val for sub in daily_hrv.values() for val in sub]
    all_vo2 = [val for sub in daily_vo2max.values() for val in sub]
    all_spo2 = [val for sub in daily_spo2.values() for val in sub]
    all_asym = [val for sub in daily_walking_asym.values() for val in sub]
    all_sleep = [val / 3600.0 for val in daily_sleep_total.values() if val > 0]

    def avg_val(lst, r=1):
        return round(sum(lst) / len(lst), r) if lst else None

    summary = {
        "startDate": start_date,
        "endDate": end_date,
        "totalDays": total_days,
        "totalSteps": int(total_steps),
        "avgDailySteps": int(total_steps / total_days) if total_days else 0,
        "totalDistanceKm": round(total_dist, 1),
        "totalCalories": int(total_all_cal),
        "totalActiveCalories": int(total_active_cal),
        "totalWorkouts": len(workouts_list),
        "avgRestingHR": avg_val(all_rhr),
        "avgHRV": avg_val(all_hrv),
        "avgSleep": avg_val(all_sleep),
        "avgVO2Max": avg_val(all_vo2),
        "avgOxygenSaturation": avg_val(all_spo2),
        "avgWalkingAsymmetry": avg_val(all_asym)
    }

    sorted_workouts = sorted(workouts_list, key=lambda x: x["日付"], reverse=True)[:1000]

    return {
        "summary": summary,
        "monthly": monthly_result,
        "yearly": yearly_result,
        "weekday": weekday_result,
        "workoutSummary": workout_summary,
        "workouts": sorted_workouts
    }


def encrypt_payload(data_dict, password):
    """
    JSONデータを AES-256-GCM (PBKDF2 100,000 iter, Salt 16B, IV 12B) で暗号化し Base64 文字列を返す
    """
    print("[INFO] データを AES-256-GCM で暗号化中...")
    json_bytes = json.dumps(data_dict, ensure_ascii=False).encode("utf-8")

    salt = os.urandom(16)
    iv = os.urandom(12)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    key = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, json_bytes, None)

    encrypted_package = salt + iv + ciphertext
    import base64
    return base64.b64encode(encrypted_package).decode("ascii")


def update_html(template_path, output_path, encrypted_payload):
    """index.html の ENCRYPTED_PAYLOAD を新しい暗号文に更新"""
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    new_html = re.sub(
        r'const ENCRYPTED_PAYLOAD\s*=\s*"[^"]*"',
        f'const ENCRYPTED_PAYLOAD = "{encrypted_payload}"',
        html_content
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"[SUCCESS] ダッシュボード HTML を正常に出力しました: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Apple Health Export Data Processor & Secure Dashboard Builder"
    )
    parser.add_argument("-i", "--input", help="入力ファイルパス (export.zip または export.xml)")
    parser.add_argument("-p", "--password", default="applehealth2026", help="暗号化パスワード (デフォルト: applehealth2026)")
    parser.add_argument("-t", "--template", default="index.html", help="HTMLテンプレートパス (デフォルト: index.html)")
    parser.add_argument("-o", "--output", default="index.html", help="出力先HTMLパス (デフォルト: index.html)")
    parser.add_argument("--json-out", help="集計した未暗号化JSONを保存するパス（オプション）")

    args = parser.parse_args()

    if not args.input:
        candidates = ["export.zip", "apple_health_export/export.xml", "export.xml"]
        for c in candidates:
            if os.path.exists(c):
                args.input = c
                break

    if not args.input or not os.path.exists(args.input):
        print("[ERROR] 入力ファイルが指定されていないか、見つかりません。")
        print("使用法: python process_export.py -i <export.zip または export.xml> -p <パスワード>")
        sys.exit(1)

    stream, zip_ref = get_xml_stream(args.input)
    try:
        data = process_health_data(stream)
    finally:
        stream.close()
        if zip_ref:
            zip_ref.close()

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[INFO] JSONデータを保存しました: {args.json_out}")

    encrypted_b64 = encrypt_payload(data, args.password)
    update_html(args.template, args.output, encrypted_b64)
    print("[SUCCESS] すべての処理が正常に完了しました！")


if __name__ == "__main__":
    main()
