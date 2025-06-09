from fastapi import FastAPI, Query, HTTPException
import json
import datetime
import re
from dateutil import parser
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from logging.handlers import RotatingFileHandler


def is_valid_ip(ip):
    pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
    ip_match = re.search(pattern, ip)
    return ip_match.group(0) if ip_match else ip


def update_data():
    data = open_json_file(json_file_path)

    filtered_data = delete_print_to_pdf_records(data)
    filtered_data = sort_data_by_time_created(filtered_data)
    filtered_data = data_processing(filtered_data)

    with open(new_data_file, 'w', encoding='utf-8-sig') as new_file:
        json.dump(filtered_data, new_file, ensure_ascii=False, indent=4)

    logger.info("The data has been updated.")


def open_json_file(file_path):
    with open(file_path, encoding='utf-8-sig') as f:
        return json.load(f)


def delete_print_to_pdf_records(data):
    return [record for record in data if record['PrinterName'] != "Microsoft Print to PDF"]


def sort_data_by_time_created(data):
    return sorted(data, key=lambda x: x['TimeCreated'], reverse=True)


def data_processing(data):
    for item in data:
        item.pop('PSShowComputerName', None)
        item.pop('RunspaceId', None)
        time_created_str = item['TimeCreated']
        timestamp = int(time_created_str[6:-2]) / 1000
        item['TimeCreated'] = datetime.datetime.fromtimestamp(timestamp).isoformat()
        item['Port'] = is_valid_ip(item['Port'])
        item['PrintSizeKb'] = int(item['PrintSizeKb'])

    return data


handler = RotatingFileHandler('ServerPrintLogAPI.log', maxBytes=1*1024*1024, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

app = FastAPI()
scheduler = BackgroundScheduler()
scheduler.add_job(update_data, 'interval', seconds=25400)
scheduler.start()
json_file_path = 'data.json'
new_data_file = 'new_data.json'


@app.get("/")
def read_root():
    logger.info("Request to the root route")
    return {"message": "Сервер работает!"}


@app.get("/print-log/")
def print_log(start_date: str = Query(None), end_date: str = Query(None), filter_type: str = None, value: str = None):
    data = open_json_file(new_data_file)

    logger_info = init_logger_info(start_date, end_date, filter_type, value)

    check_dates(start_date, end_date)

    filtered_data = filter_data_by_dates(data, start_date, end_date, logger_info)

    if start_date and end_date and filter_type and value:
        logger_info += '&'

    filtered_data = filter_type_and_value(filtered_data, filter_type, value, logger_info)

    logger.info(logger_info)

    return filtered_data


def init_logger_info(start_date=None, end_date=None, filter_type=None, value=None):
    logger_info = "Route request /print-log/"

    if start_date and end_date or filter_type and value:
        logger_info += '?'

    return logger_info


def check_dates(start_date=None, end_date=None):
    check_validate_dates(start_date, end_date)
    check_range_dates(start_date, end_date)


def check_validate_dates(start_date=None, end_date=None):
    if (start_date and not end_date) or (end_date and not start_date):
        logger.error("Both dates must be specified: start_date and end_date.")
        raise HTTPException(status_code=400, detail="Необходимо указать обе даты: start_date и end_date.")


def check_range_dates(start_date=None, end_date=None):
    if start_date and end_date:
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="Дата начала не может быть позже даты конца.")


def filter_data_by_dates(data, start_date=None, end_date=None, logger_info=None):
    filtered_data = data

    if start_date and end_date:
        start = parser.isoparse(start_date)
        end = parser.isoparse(end_date)
        filtered_data = [entry for entry in data if start <= parser.isoparse(entry['TimeCreated']) <= end]
        logger_info += f"start_date={start_date}&end_date={end_date}"

    return filtered_data


def filter_type_and_value(filtered_data, filter_type=None, value=None, logger_info=None):
    if filter_type and value:
        filter_key = 'Port' if filter_type == 'printer' else 'UserName' if filter_type == 'user' else None

        if filter_key:
            filtered_data = [entry for entry in filtered_data if entry[filter_key] == value]
            logger_info += f"filter_type={filter_type}&value={value}"
            logger.info(logger_info)
        else:
            logger.error(f"Invalid filter type: {filter_type}")
            raise HTTPException(status_code=400, detail=f"Неверный тип фильтра: {filter_type}")
    elif filter_type and not value:
        logger.error(f"The filter value is missing")
        raise HTTPException(status_code=400, detail="Отсутствует значение фильтра")
    elif value and not filter_type:
        logger.error(f"The filter is missing")
        raise HTTPException(status_code=400, detail="Отсутствует фильтр")

    return filtered_data


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()
    logger.info("ServerPrintLogAPI shutdown")


if __name__ == "__main__":
    import uvicorn
    logger.info("ServerPrintLogAPI started")
    update_data()
    uvicorn.run(app, host="0.0.0.0", port=8001)
