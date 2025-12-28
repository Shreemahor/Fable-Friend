from gradio_client import Client, handle_file

client = Client("https://5f6ac96e9533c5458b.gradio.live/")
result = client.predict(
	message={"text":"What are elephants?"},
	api_name="/open_api_stream"
)
print(result)
