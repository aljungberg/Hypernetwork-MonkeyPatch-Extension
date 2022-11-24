import html
import os

from modules import shared, sd_hijack, devices
from modules.paths import script_path
from modules.ui import create_refresh_button, gr_show
from webui import wrap_gradio_gpu_call
from .textual_inversion import train_embedding as train_embedding_external
from .hypernetwork import train_hypernetwork as train_hypernetwork_external
import gradio as gr


def train_hypernetwork_ui(*args):

    initial_hypernetwork = shared.loaded_hypernetwork

    assert not shared.cmd_opts.lowvram, 'Training models with lowvram is not possible'

    try:
        sd_hijack.undo_optimizations()

        hypernetwork, filename = train_hypernetwork_external(*args)

        res = f"""
Training {'interrupted' if shared.state.interrupted else 'finished'} at {hypernetwork.step} steps.
Hypernetwork saved to {html.escape(filename)}
"""
        return res, ""
    except Exception:
        raise
    finally:
        shared.loaded_hypernetwork = initial_hypernetwork
        shared.sd_model.cond_stage_model.to(devices.device)
        shared.sd_model.first_stage_model.to(devices.device)
        sd_hijack.apply_optimizations()


def on_train_gamma_tab(params=None):
    with gr.Tab(label="Train_Gamma") as train_gamma:
        gr.HTML(
            value="<p style='margin-bottom: 0.7em'>Train an embedding or Hypernetwork; you must specify a directory with a set of 1:1 ratio images <a href=\"https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Textual-Inversion\" style=\"font-weight:bold;\">[wiki]</a></p>")
        with gr.Row():
            train_embedding_name = gr.Dropdown(label='Embedding', elem_id="train_embedding", choices=sorted(
                sd_hijack.model_hijack.embedding_db.word_embeddings.keys()))
            create_refresh_button(train_embedding_name,
                                  sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings, lambda: {
                    "choices": sorted(sd_hijack.model_hijack.embedding_db.word_embeddings.keys())},
                                  "refresh_train_embedding_name")
        with gr.Row():
            train_hypernetwork_name = gr.Dropdown(label='Hypernetwork', elem_id="train_hypernetwork",
                                                  choices=[x for x in shared.hypernetworks.keys()])
            create_refresh_button(train_hypernetwork_name, shared.reload_hypernetworks,
                                  lambda: {"choices": sorted([x for x in shared.hypernetworks.keys()])},
                                  "refresh_train_hypernetwork_name")
        with gr.Row():
            embedding_learn_rate = gr.Textbox(label='Embedding Learning rate',
                                              placeholder="Embedding Learning rate", value="0.005")
            hypernetwork_learn_rate = gr.Textbox(label='Hypernetwork Learning rate',
                                                 placeholder="Hypernetwork Learning rate", value="0.00001")
            use_beta_scheduler_checkbox = gr.Checkbox(
                label='Show advanced learn rate scheduler options(for Hypernetworks)')
        with gr.Row(visible=False) as beta_scheduler_options:
            use_beta_scheduler = gr.Checkbox(label='Uses CosineAnnealingWarmRestarts Scheduler')
            beta_repeat_epoch = gr.Textbox(label='Epoch for cycle', placeholder="Cycles every nth epoch", value="4000")
            min_lr = gr.Textbox(label='Minimum learning rate for beta scheduler',
                                placeholder="restricts decay value, but does not restrict gamma rate decay",
                                value="1e-7")
            gamma_rate = gr.Textbox(label='Separate learning rate decay for ExponentialLR',
                                    placeholder="Value should be in (0-1]", value="1")
        use_beta_scheduler_checkbox.change(
            fn=lambda show: gr_show(show),
            inputs=[use_beta_scheduler_checkbox],
            outputs=[beta_scheduler_options],
        )
        batch_size = gr.Number(label='Batch size', value=1, precision=0)
        gradient_step = gr.Number(label='Gradient accumulation steps', value=1, precision=0)
        dataset_directory = gr.Textbox(label='Dataset directory', placeholder="Path to directory with input images")
        log_directory = gr.Textbox(label='Log directory', placeholder="Path to directory where to write outputs",
                                   value="textual_inversion")
        template_file = gr.Textbox(label='Prompt template file',
                                   value=os.path.join(script_path, "textual_inversion_templates",
                                                      "style_filewords.txt"))
        training_width = gr.Slider(minimum=64, maximum=2048, step=64, label="Width", value=512)
        training_height = gr.Slider(minimum=64, maximum=2048, step=64, label="Height", value=512)
        steps = gr.Number(label='Max steps', value=100000, precision=0)
        create_image_every = gr.Number(label='Save an image to log directory every N steps, 0 to disable',
                                       value=500, precision=0)
        save_embedding_every = gr.Number(
            label='Save a copy of embedding to log directory every N steps, 0 to disable', value=500, precision=0)
        save_image_with_stored_embedding = gr.Checkbox(label='Save images with embedding in PNG chunks', value=True)
        preview_from_txt2img = gr.Checkbox(
            label='Read parameters (prompt, etc...) from txt2img tab when making previews', value=False)
        with gr.Row():
            shuffle_tags = gr.Checkbox(label="Shuffle tags by ',' when creating prompts.", value=False)
            tag_drop_out = gr.Slider(minimum=0, maximum=1, step=0.1, label="Drop out tags when creating prompts.",
                                     value=0)
        with gr.Row():
            latent_sampling_method = gr.Radio(label='Choose latent sampling method', value="once",
                                              choices=['once', 'deterministic', 'random'])

        with gr.Row():
            interrupt_training = gr.Button(value="Interrupt")
            train_hypernetwork = gr.Button(value="Train Hypernetwork", variant='primary')
            train_embedding = gr.Button(value="Train Embedding", variant='primary')
        ti_output = gr.Text(elem_id="ti_output3", value="", show_label=False)
        ti_outcome = gr.HTML(elem_id="ti_error3", value="")


    train_embedding.click(
        fn=wrap_gradio_gpu_call(train_embedding_external, extra_outputs=[gr.update()]),
        _js="start_training_textual_inversion",
        inputs=[
            train_embedding_name,
            embedding_learn_rate,
            batch_size,
            gradient_step,
            dataset_directory,
            log_directory,
            training_width,
            training_height,
            steps,
            shuffle_tags,
            tag_drop_out,
            latent_sampling_method,
            create_image_every,
            save_embedding_every,
            template_file,
            save_image_with_stored_embedding,
            preview_from_txt2img,
            *params.txt2img_preview_params,
        ],
        outputs=[
            ti_output,
            ti_outcome,
        ]
    )

    train_hypernetwork.click(
        fn=wrap_gradio_gpu_call(train_hypernetwork_ui, extra_outputs=[gr.update()]),
        _js="start_training_textual_inversion",
        inputs=[
            train_hypernetwork_name,
            hypernetwork_learn_rate,
            batch_size,
            gradient_step,
            dataset_directory,
            log_directory,
            training_width,
            training_height,
            steps,
            shuffle_tags,
            tag_drop_out,
            latent_sampling_method,
            create_image_every,
            save_embedding_every,
            template_file,
            preview_from_txt2img,
            *params.txt2img_preview_params,
            use_beta_scheduler,
            beta_repeat_epoch,
            min_lr,
            gamma_rate
        ],
        outputs=[
            ti_output,
            ti_outcome,
        ]
    )

    interrupt_training.click(
        fn=lambda: shared.state.interrupt(),
        inputs=[],
        outputs=[],
    )
    return [(train_gamma, "Train Gamma", "train_gamma")]