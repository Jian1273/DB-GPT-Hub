import os
import json
import jsonlines
import sys

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_PATH)

from tqdm import tqdm

from dbgpt_hub.configs.config import (
    SQL_DATA_INFO,
    DATA_PATH,
    INPUT_PROMPT,
    INSTRUCTION_PROMPT,
)


class ProcessSqlData:
    def __init__(self, train_file=None, dev_file=None) -> None:
        self.train_file = train_file
        self.dev_file = dev_file

    def decode_json_file(
        self, data_file_list, table_file, db_id_name, is_multiple_turn=False
    ):
        """
        TO DO:
            1.将相关prompt放入config中
            2.将不同数据来源的字段信息放入config中
        """

        if table_file.endswith(".jsonl"):
            tables = jsonlines.open(table_file)
            datas = []
            for data_file in data_file_list:
                datas.extend(jsonlines.open(data_file))

        elif table_file.endswith(".json"):
            tables = json.load(open(table_file))
            datas = []
            for data_file in data_file_list:
                datas.extend(json.load(open(data_file)))
        else:
            print("Unsupported file types")
            raise

        # 先将db_id 的table和coloumns处理好
        db_dict = {}
        for item in tables:
            tables = item["table_names_original"]
            coloumns = item["column_names_original"][1:]
            primary_key = item["primary_keys"]
            foreign_keys = item["foreign_keys"]
            source = (
                item["db_id"] + " contains tables such as " + ", ".join(tables) + ". "
            )
            for i, name in enumerate(tables):
                data = [coloumn[1] for coloumn in coloumns if coloumn[0] == i]
                source += (
                    "Table " + name + " has columns such as " + ", ".join(data) + ". "
                )

                # get primary key info
                for j in range(len(primary_key)):
                    if coloumns[primary_key[j] - 1][0] == i:
                        source += (
                            coloumns[primary_key[j] - 1][1]
                            + " is the primary key."
                            + "\n"
                        )

            # get foreign key info
            for key in foreign_keys:
                source += (
                    "The "
                    + coloumns[key[0] - 1][1]
                    + " of "
                    + tables[coloumns[key[0] - 1][0]]
                    + " is the foreign key of "
                    + coloumns[key[1] - 1][1]
                    + " of "
                    + tables[coloumns[key[1] - 1][0]]
                    + ".\n"
                )

            db_dict[item["db_id"]] = source

        res = []
        for data in tqdm(datas):
            if data[db_id_name] in db_dict.keys():
                if is_multiple_turn:  # 多轮
                    history = []
                    for interaction in data["interaction"]:
                        input = {
                            "db_id": data[db_id_name],
                            "instruction": INSTRUCTION_PROMPT.format(
                                db_dict[data[db_id_name]]
                            ),
                            "input": INPUT_PROMPT.format(interaction["utterance"]),
                            "output": interaction["query"],
                            "history": history,
                        }
                        res.append(input)
                        history.append(
                            (
                                INPUT_PROMPT.format(interaction["utterance"]),
                                interaction["query"],
                            )
                        )
                else:  # 单轮
                    input = {
                        "db_id": data[db_id_name],
                        "instruction": INSTRUCTION_PROMPT.format(
                            db_dict[data[db_id_name]]
                        ),
                        "input": INPUT_PROMPT.format(data["question"]),
                        "output": data["query"],
                        "history": [],
                    }
                    res.append(input)
        return res

    def create_sft_raw_data(self):
        train_data = []
        dev_data = []
        for data_info in SQL_DATA_INFO:
            train_data_file_list = [
                os.path.join(DATA_PATH, data_info["data_source"], file)
                for file in data_info["train_file"]
            ]
            train_data.extend(
                self.decode_json_file(
                    data_file_list=train_data_file_list,
                    table_file=os.path.join(
                        DATA_PATH, data_info["data_source"], data_info["tables_file"]
                    ),
                    db_id_name=data_info["db_id_name"],
                    is_multiple_turn=data_info["is_multiple_turn"],
                )
            )

            dev_data_file_list = [
                os.path.join(DATA_PATH, data_info["data_source"], file)
                for file in data_info["dev_file"]
            ]
            dev_data.extend(
                self.decode_json_file(
                    data_file_list=dev_data_file_list,
                    table_file=os.path.join(
                        DATA_PATH, data_info["data_source"], data_info["tables_file"]
                    ),
                    db_id_name=data_info["db_id_name"],
                    is_multiple_turn=data_info["is_multiple_turn"],
                )
            )
        with open(self.train_file, "w", encoding="utf-8") as s:
            json.dump(train_data, s, indent=4, ensure_ascii=False)
        with open(self.dev_file, "w", encoding="utf-8") as s:
            json.dump(dev_data, s, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    all_in_one_train_file = os.path.join(DATA_PATH, "example_text2sql_train.json")
    all_in_one_dev_file = os.path.join(DATA_PATH, "example_text2sql_dev.json")
    precess = ProcessSqlData(
        train_file=all_in_one_train_file, dev_file=all_in_one_dev_file
    )
    precess.create_sft_raw_data()
