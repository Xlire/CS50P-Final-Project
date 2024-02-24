import os.path
import pandas as pd
import shutil
import argparse
import csv
import base64
from typing import List
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class NoEmailFound(Exception):
    """no email found"""


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://mail.google.com/"]
current_user = ""


def search_emails(service, query_string: str, label_ids=None):
    try:
        message_list_response = (
            service.users()
            .messages()
            .list(userId=current_user, labelIds=label_ids, q=query_string)
            .execute()
        )

        message_items = message_list_response.get("messages")
        next_page_token = message_list_response.get("nextPageToken")

        while next_page_token:
            message_list_response = (
                service.users()
                .messages()
                .list(
                    userId=current_user,
                    labelIds=label_ids,
                    q=query_string,
                    pageToken=next_page_token,
                )
                .execute()
            )

            message_items.extend(message_list_response.get("messages"))
            next_page_token = message_list_response.get("nextPageToken")
        return message_items
    except Exception as e:
        raise NoEmailFound("No emails returned")


def get_file_data(service, message_id, attachment_id, file_name, save_location):
    response = (
        service.users()
        .messages()
        .attachments()
        .get(userId=current_user, messageId=message_id, id=attachment_id)
        .execute()
    )

    file_data = base64.urlsafe_b64decode(response.get("data").encode("UTF-8"))
    return file_data


def get_message_detail(
    service, message_id, msg_format="metadata", metadata_headers: List = None
):
    message_detail = (
        service.users()
        .messages()
        .get(
            userId=current_user,
            id=message_id,
            format=msg_format,
            metadataHeaders=metadata_headers,
        )
        .execute()
    )
    return message_detail


def main():
    parser = argparse.ArgumentParser(
        description="Recieve and delete email has attachments"
    )
    parser.add_argument("-u", help="update new mail", action="store_true")
    parser.add_argument("-rm", help="remove done in orders.csv", action="store_true")
    parser.add_argument("-s", "--show", help="show orders")
    args = parser.parse_args()
    if args.u:
        update_order()
    if args.rm:
        remove_order()
    if args.show:
        df = pd.read_csv("/workspaces/112750129/cs50p/final/orders.csv")
        if args.show == "a":
            df_len = len(df['message_id'].tolist())
            print(df.head(df_len))
        else:
            print(df.head(int(args.show)))


def update_order():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    save_location = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__))
    )
    creds = None
    global current_user

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists("/workspaces/112750129/cs50p/final/token.json"):
        creds = Credentials.from_authorized_user_file(
            "/workspaces/112750129/cs50p/final/token.json", SCOPES
        )
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "/workspaces/112750129/cs50p/final/credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

    # Save the credentials for the next run
    with open("token.json", "w") as token:
        token.write(creds.to_json())

    try:
        # Call the Gmail API
        service = build("gmail", "v1", credentials=creds)
        result = service.users().getProfile(userId=current_user).execute()
        current_user = result["emailAddress"]
    except Exception as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f"An error occurred: {error}")

    query_string = "has:attachment"
    email_messages = search_emails(service, query_string)

    with open("orders.csv", "a") as file:
        # TODO if arg -rm then delele done order (& send email for that customer)
        writer = csv.DictWriter(
            file, fieldnames=["message_id", "files_num", "snippet", "done"]
        )
        if file.tell() == 0:
            writer.writeheader()
        for email_message in email_messages:
            files_num = 0
            # can simpify by seeing order_code in orders.csv

            messageDetail = get_message_detail(
                service,
                email_message["id"],
                msg_format="full",
                metadata_headers=["parts"],
            )
            message_id = messageDetail["id"]

            with open("readed_id.csv", "r") as file2:
                df = pd.read_csv(file2)
                if message_id not in df["message_id"].tolist():
                    os.makedirs(f"/workspaces/112750129/cs50p/final/order/{message_id}")
                    with open("readed_id.csv", "a") as file2:
                        writer2 = csv.DictWriter(file2, fieldnames=["message_id"])
                        writer2.writerow({"message_id": message_id})
                else:
                    continue

            snippet = messageDetail["snippet"]
            messageDetailPayload = messageDetail.get("payload")
            if "parts" in messageDetailPayload:
                for msgPayload in messageDetailPayload["parts"]:
                    file_name = msgPayload["filename"]
                    body = msgPayload["body"]
                    if "attachmentId" in body:
                        attachment_id = body["attachmentId"]
                        attachment_content = get_file_data(
                            service,
                            email_message["id"],
                            attachment_id,
                            file_name,
                            save_location,
                        )
                        with open(
                            os.path.join(save_location, "order", message_id, file_name),
                            "wb",
                        ) as _f:
                            _f.write(attachment_content)
                            print(
                                f"File {file_name} is saved at {save_location}/order/{message_id}"
                            )
                        files_num += 1
                writer.writerow(
                    {
                        "message_id": message_id,
                        "files_num": files_num,
                        "snippet": snippet,
                        "done": "n",
                    }
                )


def remove_order():
    df = pd.read_csv("/workspaces/112750129/cs50p/final/orders.csv")
    drop_list = df.index[df["done"] == "y"].tolist()
    message_ids = df.loc[drop_list, "message_id"].tolist()
    for message_id in message_ids:
        print(f"remover order with id: {message_id}")
        shutil.rmtree(f"/workspaces/112750129/cs50p/final/order/{message_id}")

    df2 = df.drop(drop_list)
    df2.to_csv("orders.csv", index=False)


if __name__ == "__main__":
    main()

message_detail = {
    "id": "mock",
    "threadId": "mock",
    "labelIds": ["IMPORTANT", "CATEGORY_PERSONAL", "INBOX"],
    "snippet": "mock",
    "payload": {
        "partId": "",
        "mimeType": "multipart/mixed",
        "filename": "",
        "headers": [
            {"name": "Delivered-To", "value": "aadatoanthien@gmail.com"},
            {
                "name": "Received",
                "value": "by 2002:a2e:99c5:0:b0:2d0:f949:789e with SMTP id l5csp694619ljj;        Mon, 12 Feb 2024 23:29:22 -0800 (PST)",
            },
            {
                "name": "X-Received",
                "value": "by 2002:a0d:d70d:0:b0:602:ac9e:d626 with SMTP id z13-20020a0dd70d000000b00602ac9ed626mr1240582ywd.21.1707809360830;        Mon, 12 Feb 2024 23:29:20 -0800 (PST)",
            },
            {
                "name": "ARC-Seal",
                "value": "i=1; a=rsa-sha256; t=1707809360; cv=none;        d=google.com; s=arc-20160816;        b=XVfEQCQjzr9E8rWnmFP0/zrIbgvE7zJuBX7v5cs4B94rfDIunMixeYOaAehkxhiKb1         P565CzNao5AfGtHPwo7VRT+VAvBePExCWyMTSarCgKImBq7KlL77y7U2w9jlq0ZHg+Rj         hgDlGO7UQ9AcU8OlfLXLOTYhTBpJOLHgnwrhVxkSZTYxBFGR1yO3oJnwgETQbz5g5heT         Y7WxC0ECCNJG1+MYs8P0iwq50zXK6DLn8NlJ2nFMWGNMFyGDiFZNvx3UaCMjsFACi0Rv         PQl92IqtXyeTzmJ7Y08KKVqoBekD7D2GvaFVd9XvUBBUKLO3yBt+NU/kfN2sVDcUmxxh         GqMw==",
            },
            {
                "name": "ARC-Message-Signature",
                "value": "i=1; a=rsa-sha256; c=relaxed/relaxed; d=google.com; s=arc-20160816;        h=to:subject:message-id:date:from:mime-version:dkim-signature;        bh=7szjon7vhA0LzLzgl4a2/BNndS1m8nl1stx0WAtJB3c=;        fh=6lBXHEpLSQTLx/mv1iViLkFPaqhxaEnSGT0a++THnn0=;        b=Y5bN2cfSxBbP+hxPPpAZOWUP3fBH8VUsMx8HZ1uzuoGYeCakIdomNqT3gXfzm3YI7B         ZzFSsWaJ4MNbYzHP1nBp+AQ6KkY7yMJL4EyOhVAmddcJxbkhUtWRSLxtz7eXQ5KmtXB2         M/EYXZlx2h7FvU4lBmPsm1fABOJNYHHBUXkoK5nLiflWKssiVe7PxPAMyr2uyxLaVebG         A/m9qjnTEK6oj0LSPNXngUCLrrRyoGYBwXE8ftfCREuOHQB++4yHQsEUzbInqAZkcBp/         ARzm+6dgQIPYh6C0pzuMUaNepzEbxEWD8tf45fFAQOeLXQECi6PO129DXMNAGWPHmPep         fnIA==;        dara=google.com",
            },
            {
                "name": "ARC-Authentication-Results",
                "value": "i=1; mx.google.com;       dkim=pass header.i=@gmail.com header.s=20230601 header.b=BmKKOGoL;       spf=pass (google.com: domain of xanh285@gmail.com designates 209.85.220.41 as permitted sender) smtp.mailfrom=xanh285@gmail.com;       dmarc=pass (p=NONE sp=QUARANTINE dis=NONE) header.from=gmail.com",
            },
            {"name": "Return-Path", "value": "<xanh285@gmail.com>"},
            {
                "name": "Received",
                "value": "from mail-sor-f41.google.com (mail-sor-f41.google.com. [209.85.220.41])        by mx.google.com with SMTPS id i187-20020a816dc4000000b0060496689a0fsor2050877ywc.7.2024.02.12.23.29.20        for <aadatoanthien@gmail.com>        (Google Transport Security);        Mon, 12 Feb 2024 23:29:20 -0800 (PST)",
            },
            {
                "name": "Received-SPF",
                "value": "pass (google.com: domain of xanh285@gmail.com designates 209.85.220.41 as permitted sender) client-ip=209.85.220.41;",
            },
            {
                "name": "Authentication-Results",
                "value": "mx.google.com;       dkim=pass header.i=@gmail.com header.s=20230601 header.b=BmKKOGoL;       spf=pass (google.com: domain of xanh285@gmail.com designates 209.85.220.41 as permitted sender) smtp.mailfrom=xanh285@gmail.com;       dmarc=pass (p=NONE sp=QUARANTINE dis=NONE) header.from=gmail.com",
            },
            {
                "name": "DKIM-Signature",
                "value": "v=1; a=rsa-sha256; c=relaxed/relaxed;        d=gmail.com; s=20230601; t=1707809360; x=1708414160; dara=google.com;        h=to:subject:message-id:date:from:mime-version:from:to:cc:subject         :date:message-id:reply-to;        bh=7szjon7vhA0LzLzgl4a2/BNndS1m8nl1stx0WAtJB3c=;        b=BmKKOGoLvkfEy1nfAzV8BktqJNjbYoCGudOwdcpbqJ6PIc/ea+PFcAsCFguLsHUFoP         HIhxb7CSb1jfkuYUyBCdWAuy//LTGjDxEcfNRWGvEepNqdtmPqCR97UUgEdUL71l2K0x         9dyPdNUVGBFVbsbve0CsUn/R6/TsgVNhGwV26O5AXbV2aHG0ZUHf/V8lj0E3qohLp1Kr         jUz2jfiRcCpK2O2+FcXdMX8NrROn1xrARguVD5wUayDM5EtghCT6uf5NzoCgnMUCFjk0         Rhybv5AtUalWv9TqXnniK8j5xZRtt59ZcjeWGKZwvA4/3b6+lkQsbbyULA0A7MtaAxPo         LxPw==",
            },
            {
                "name": "X-Google-DKIM-Signature",
                "value": "v=1; a=rsa-sha256; c=relaxed/relaxed;        d=1e100.net; s=20230601; t=1707809360; x=1708414160;        h=to:subject:message-id:date:from:mime-version:x-gm-message-state         :from:to:cc:subject:date:message-id:reply-to;        bh=7szjon7vhA0LzLzgl4a2/BNndS1m8nl1stx0WAtJB3c=;        b=SyFAgV83N2Ma0V/qwE5iW3wOHIpElidYecWsQ7RODCe+3MMNW5MhW0WkfKMeOL35Q7         FOgr4wczgtTd5GOrgcjdFdIVwA0Mvcl1bs4VsIjI+Sz12AnF+u88vP8qcHf+b5OYR9Dh         orT6Bow/HjAF/bxzU0IYlB6XmqLdKY9U5lzsx68oG6DUxVwp/QvHYHiaWcil0cAIWJzG         3QKP5TsOnpd9qVekWiXB7eoYJpEDCOkSbr3DUnjAcF2AijG5LHBH9dzuveFHJpNvs7Ra         tccCXR/AZDUinW2Wq0DxQYeCorue8SA8RNu3uUiYfYkiA9+VmtoVpDaZMepoyHaQrLc0         PnRg==",
            },
            {
                "name": "X-Gm-Message-State",
                "value": "AOJu0Yz1503QHGBOhZ/fmCLgzIWXoWMYzkvvBJO3+CODrMf/lYnSB1U0 wuS8+WJtO/yz27CDHcLjddcvtae0QFkGoJlR7QI7ZwPWqdFxQVdo6LpD0/xOr3Imqn22aieHAKz M9j9ADY7UseBZt+iy90IpXu6NehDUSSwa",
            },
            {
                "name": "X-Google-Smtp-Source",
                "value": "AGHT+IGES0OsQHTlH8srZxcVN5/kGN4h3bE9coS09DR8yFOsxVMGmuS8tB8dX1BJWll0aGJnR23FSWNb0m74oKffzJM=",
            },
            {
                "name": "X-Received",
                "value": "by 2002:a81:4904:0:b0:604:95db:c4c5 with SMTP id w4-20020a814904000000b0060495dbc4c5mr1073691ywa.25.1707809359450; Mon, 12 Feb 2024 23:29:19 -0800 (PST)",
            },
            {"name": "MIME-Version", "value": "1.0"},
            {"name": "From", "value": '"Thiện Toàn Vũ" <xanh285@gmail.com>'},
            {"name": "Date", "value": "Tue, 13 Feb 2024 14:31:55 +0700"},
            {
                "name": "Message-ID",
                "value": "<CAErM_wWLj5LOD0wcKTrJta8_GALHx0+vUdq_YiCL7ozpJe4mdg@mail.gmail.com>",
            },
            {"name": "Subject", "value": "in lan 2"},
            {
                "name": "To",
                "value": '"aadatoanthien@gmail.com" <aadatoanthien@gmail.com>',
            },
            {
                "name": "Content-Type",
                "value": 'multipart/mixed; boundary="00000000000037962606113e5acf"',
            },
        ],
        "body": {"size": 0},
        "parts": [
            {
                "partId": "0",
                "mimeType": "multipart/alternative",
                "filename": "",
                "headers": [
                    {
                        "name": "Content-Type",
                        "value": 'multipart/alternative; boundary="00000000000037962406113e5acd"',
                    }
                ],
                "body": {"size": 0},
                "parts": [
                    {
                        "partId": "0.0",
                        "mimeType": "text/plain",
                        "filename": "",
                        "headers": [
                            {
                                "name": "Content-Type",
                                "value": 'text/plain; charset="UTF-8"',
                            }
                        ],
                        "body": {"size": 12, "data": "SW4gZ2FwIFNPUw0K"},
                    },
                    {
                        "partId": "0.1",
                        "mimeType": "text/html",
                        "filename": "",
                        "headers": [
                            {
                                "name": "Content-Type",
                                "value": 'text/html; charset="UTF-8"',
                            },
                            {
                                "name": "Content-Transfer-Encoding",
                                "value": "quoted-printable",
                            },
                        ],
                        "body": {
                            "size": 35,
                            "data": "PGRpdiBkaXI9Imx0ciI-SW4gZ2FwIFNPU8KgPC9kaXY-DQo=",
                        },
                    },
                ],
            },
            {
                "partId": "1",
                "mimeType": "application/pdf",
                "filename": "mock.pdf",
                "headers": [
                    {
                        "name": "Content-Type",
                        "value": 'application/pdf; name="Curriculum_Bachelorstudium_Circular_Engineering.pdf"',
                    },
                    {
                        "name": "Content-Disposition",
                        "value": 'attachment; filename="mock_file.pdf"',
                    },
                    {"name": "Content-Transfer-Encoding", "value": "base64"},
                    {"name": "Content-ID", "value": "<f_lsk1olly0>"},
                    {"name": "X-Attachment-Id", "value": "f_lsk1olly0"},
                ],
                "body": {
                    "attachmentId": "ANGjdJ9aVICRKpUdVHm_eH0iCKnoKr0x6oiQT2aKF4VI2sxdmDOPiFGLBkmOzLnCT37_NGtCPsaykAYNIFIeIWaltRRFOA8qCn5-9ecy7O-Lf63nPfo8KbghakLg3_nT6tzXivBnoq7byOLcwIYC0d2habmMr4rdl0ENIb-V6VyrY_30KAYUK1Tl_CIhX-yeAfncSk2F0tbFCMPfVvYHmgQTBSlCmAFJv06RA96GOQnJkRi1xd6sKKQe4VSZKabpjvAX93QNYmYdY-LBrmOSwRP0gI5N2wYOVoCNvYcZ5ZMGsUQS3W2tuLUIaHHSkuiA2Yqquc55ZUrFmC0aDYENvhnqNO7QiMNBYle-EUMPDSuCsXKZN0PQPTt85DSrxdOChKK_REdhgJ4IrqbTA1YF",
                    "size": 292885,
                },
            },
        ],
    },
    "sizeEstimate": 406529,
    "historyId": "31031",
    "internalDate": "1707809515000",
}
