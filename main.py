import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.modalview import ModalView
from kivy.lang import Builder
from kivy.uix.filechooser import FileChooserListView, FileChooserIconView
from kivy.uix.dropdown import DropDown
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock
from database import initialize_database, add_collection_to_db, get_all_tags, add_new_tag, get_all_collections
import os
import sys
import subprocess

from kivy.properties import StringProperty, NumericProperty

class CollectionCard(ButtonBehavior, BoxLayout):
    """
    A card widget to display individual collection information,
    including an image, name, tags, and a path to its folder.
    It also handles click events to open the collection's folder.
    """
    collection_id = NumericProperty(0)
    image_source = StringProperty("")
    collection_name = StringProperty("Collection Name")
    collection_tags = StringProperty("")
    folder_path = StringProperty("")

    def on_collection_tags(self, instance, value):
        """
        Kivy property observer that triggers when 'collection_tags' changes.
        Schedules the '_update_tags_display' method to run on the next frame.
        """
        Clock.schedule_once(self._update_tags_display, 0)

    def _update_tags_display(self, dt):
        """
        Updates the display of tags within the CollectionCard.
        Clears existing tags and creates new styled Label widgets for each tag.
        This method is scheduled by 'on_collection_tags' to ensure widget IDs are available.
        """
        tags_container = self.ids.get('tags_container')
        if not tags_container:
            print("Debug (Clock.schedule_once): tags_container still not found in CollectionCard ids")
            return
        tags_container.clear_widgets()
        value = self.collection_tags

        if value: 
            tag_list = [tag.strip() for tag in value.split(',') if tag.strip()]
            for tag_text in tag_list:
                tag_label = Label(
                    text=tag_text,
                    size_hint_x=None,
                    size_hint_y=None,
                    font_size='12sp',
                    color=(1, 1, 1, 1)
                )

                with tag_label.canvas.before:
                    tag_label.bg_color_instruction = Color(0.3, 0.3, 0.3, 1)
                    tag_label.bg_rect_instruction = RoundedRectangle(radius=[dp(5)])

                def update_label_size_from_texture(label, texture_size):
                    if texture_size[0] == 0 and texture_size[1] == 0:
                        return
                    label.height = texture_size[1] + dp(8)
                    label.width = texture_size[0] + dp(12)

                def update_bg_graphics(label, _):
                    label.bg_rect_instruction.pos = label.pos
                    label.bg_rect_instruction.size = label.size

                tag_label.bind(texture_size=update_label_size_from_texture)
                tag_label.bind(pos=update_bg_graphics, size=update_bg_graphics)

                tag_label.texture_update()
                update_label_size_from_texture(tag_label, tag_label.texture_size)
                update_bg_graphics(tag_label, None)

                tags_container.add_widget(tag_label)

class NewCollectionPopup(ModalView):
    """
    A popup window for creating a new collection.
    Allows users to input a name, select a folder, choose an image, and assign tags.
    """
    pass

class FolderChooserPopup(ModalView):
    """
    A popup window that allows the user to select a folder using a file chooser.
    """
    pass

class NewTagPopup(ModalView):
    """
    A popup window for creating a new tag.
    Allows users to input a name for a new tag.
    """
    pass

class ImageChooserPopup(ModalView):
    """
    A popup window that allows the user to select an image using a file chooser.
    """
    pass

class MainLayout(BoxLayout):
    """
    The main layout of the application, likely containing the grid of collections
    and controls for adding new collections.
    """
    pass

class VisualCollectionApp(App):
    """
    The main application class. Manages the overall application lifecycle,
    UI elements, and interactions between different components like popups and the main display.
    """
    current_new_collection_popup = None
    selected_folder_path = None
    tags_dropdown = None
    selected_tags_for_new_collection = set()
    current_new_tag_popup = None
    selected_image_path = None

    def build(self):
        """
        Kivy's method to build the application's UI.
        Returns the root widget of the application.
        """
        return MainLayout()

    def on_start(self):
        """
        Kivy's method called after the 'build' method is finished and the root widget is available.
        Used here to populate the initial collection grid.
        """
        self.populate_collections_grid()


    def open_new_collection_popup(self):
        """
        Opens the popup dialog for creating a new collection.
        Initializes the popup with default values and sets up its components.
        """
        popup = NewCollectionPopup()
        self.current_new_collection_popup = popup
        self.selected_tags_for_new_collection.clear()
        self.selected_image_path = None 
        if hasattr(popup.ids, 'image_preview'):
            popup.ids.image_preview.source = "assets/placeholder_popup.png"
        else:
            print("Warning: 'image_preview' not found in NewCollectionPopup ids.")

        self.create_tags_dropdown(popup)
        if hasattr(popup.ids, 'tags_button'):
            popup.ids.tags_button.bind(on_release=self.tags_dropdown.open)
            popup.ids.tags_button.text = "Select Tags"
        else:
            print("Warning: 'tags_button' not found in NewCollectionPopup ids.")
        
        if hasattr(popup.ids, 'selected_folder_label'):
            popup.ids.selected_folder_label.text = "No folder selected"
        self.selected_folder_path = None
        
        popup.open()

    def create_tags_dropdown(self, main_popup_instance):
        """
        Creates and populates the dropdown menu for selecting tags
        when creating a new collection.
        Args:
            main_popup_instance: The instance of the NewCollectionPopup where the dropdown is used.
        """
        self.tags_dropdown = DropDown()
        all_db_tags = get_all_tags()

        for tag_name in all_db_tags:
            btn = Button(text=tag_name, size_hint_y=None, height='44dp')
            btn.bind(on_release=lambda btn_instance, tn=tag_name: self.toggle_tag_selection(tn, main_popup_instance.ids.tags_button))
            self.tags_dropdown.add_widget(btn)
        
        add_new_tag_btn = Button(text="Create new tag...", size_hint_y=None, height='44dp')
        add_new_tag_btn.bind(on_release=self.prompt_for_new_tag)
        self.tags_dropdown.add_widget(add_new_tag_btn)

    def toggle_tag_selection(self, tag_name, main_tags_button_instance):
        """
        Toggles the selection state of a tag for a new collection.
        Adds or removes the tag from the 'selected_tags_for_new_collection' set
        and updates the display text of the main tags button.
        Args:
            tag_name (str): The name of the tag to toggle.
            main_tags_button_instance: The button widget that displays selected tags.
        """
        if tag_name in self.selected_tags_for_new_collection:
            self.selected_tags_for_new_collection.remove(tag_name)
        else:
            self.selected_tags_for_new_collection.add(tag_name)
        self.update_main_tags_button_text(main_tags_button_instance)
        self.tags_dropdown.dismiss()

    def update_main_tags_button_text(self, main_tags_button_instance):
        """
        Updates the text of the main button that displays selected tags
        in the NewCollectionPopup.
        Args:
            main_tags_button_instance: The button widget to update.
        """
        if not self.selected_tags_for_new_collection:
            main_tags_button_instance.text = "Select Tags"
        else:
            main_tags_button_instance.text = ", ".join(self.selected_tags_for_new_collection)

    def prompt_for_new_tag(self, instance):
        """
        Opens a popup dialog for the user to enter a new tag name.
        Args:
            instance: The widget instance that triggered this method (e.g., a button).
        """
        if self.tags_dropdown:
            self.tags_dropdown.dismiss()
        
        new_tag_popup = NewTagPopup()
        self.current_new_tag_popup = new_tag_popup
        new_tag_popup.open()

    def save_new_tag_from_popup(self, tag_name_to_save, new_tag_popup_instance):
        """
        Saves a new tag entered by the user in the NewTagPopup.
        Adds the tag to the database, updates the selected tags for the current
        new collection, and dynamically adds it to the tags dropdown.
        Args:
            tag_name_to_save (str): The name of the new tag.
            new_tag_popup_instance: The instance of the NewTagPopup.
        """
        tag_name_to_save = tag_name_to_save.strip()
        if not tag_name_to_save:
            print("New tag name cannot be empty.")
            if hasattr(new_tag_popup_instance.ids, 'new_tag_feedback_label'):
                new_tag_popup_instance.ids.new_tag_feedback_label.text = "New tag name cannot be empty."
            return

        try:
            success = add_new_tag(tag_name_to_save)
            if success:
                print(f"Tag '{tag_name_to_save}' added successfully.")
                if hasattr(new_tag_popup_instance.ids, 'new_tag_feedback_label'):
                    new_tag_popup_instance.ids.new_tag_feedback_label.text = f"Tag '{tag_name_to_save}' added."
                
                self.selected_tags_for_new_collection.add(tag_name_to_save)
                
                # Dynamically add the new tag button to the existing dropdown
                if self.tags_dropdown and self.current_new_collection_popup:
                    new_tag_button = Button(
                        text=tag_name_to_save, 
                        size_hint_y=None, 
                        height='44dp'
                    )
                    new_tag_button.bind(on_release=lambda btn_instance, tn=tag_name_to_save: self.toggle_tag_selection(tn, self.current_new_collection_popup.ids.tags_button))
                    
                    # Insert before the "Create new tag..." button if possible
                    if self.tags_dropdown.children:
                        # The last child is the "Create new tag..." button
                        # We want to insert the new tag before it.
                        # Children are in reverse order of addition for DropDown, so add to index 1 to place before last item (index 0)
                        self.tags_dropdown.add_widget(new_tag_button, index=len(self.tags_dropdown.children))

                    else:
                        self.tags_dropdown.add_widget(new_tag_button)

                # Update the main tags button text in the NewCollectionPopup
                if self.current_new_collection_popup and hasattr(self.current_new_collection_popup.ids, 'tags_button'):
                    self.update_main_tags_button_text(self.current_new_collection_popup.ids.tags_button)

                # Optionally close the "new tag" popup after a short delay or immediately
                Clock.schedule_once(lambda dt: new_tag_popup_instance.dismiss(), 0.5) # Dismiss after 0.5 seconds

            else:
                # add_new_tag returns False if tag exists or on error
                # Check if feedback label exists before trying to set its text
                if hasattr(new_tag_popup_instance.ids, 'new_tag_feedback_label'):
                    # More specific feedback could be provided by add_new_tag if needed
                    # For now, assume it's because the tag exists or a generic error
                    # We might need to refine add_new_tag to return different values for different errors
                    # Check if the tag truly exists, if add_new_tag just prints but returns False for existing
                    from database import get_all_tags as check_tags # avoid circular import issues if any
                    if tag_name_to_save.lower() in [t.lower() for t in check_tags()]:
                        new_tag_popup_instance.ids.new_tag_feedback_label.text = "Tag already exists."
                    else:
                        new_tag_popup_instance.ids.new_tag_feedback_label.text = "Error adding tag."
                print(f"Failed to add tag '{tag_name_to_save}'. It might already exist or there was a DB error.")

        except Exception as e:
            print(f"Error adding new tag: {e}")
            if hasattr(new_tag_popup_instance.ids, 'new_tag_feedback_label'):
                new_tag_popup_instance.ids.new_tag_feedback_label.text = "Error adding tag."

    def open_folder_chooser_popup(self):
        """
        Opens a popup dialog for the user to select a folder for the new collection.
        """
        folder_popup = FolderChooserPopup()
        folder_popup.open()

    def select_folder(self, selection, folder_popup_instance):
        """
        Handles the selection of a folder from the FolderChooserPopup.
        Updates the selected folder path and the corresponding label in the NewCollectionPopup.
        Also attempts to pre-fill the collection name based on the folder name.
        Args:
            selection (list): A list containing the path(s) of the selected folder(s).
                              Expected to contain one folder path.
            folder_popup_instance: The instance of the FolderChooserPopup.
        """
        if selection:
            self.selected_folder_path = selection[0]
            print(f"Selected folder: {self.selected_folder_path}")
            if self.current_new_collection_popup:
                # Update the label in the main collection popup
                if self.current_new_collection_popup and hasattr(self.current_new_collection_popup.ids, 'selected_folder_label'):
                    self.current_new_collection_popup.ids.selected_folder_label.text = self.selected_folder_path
                
                # Attempt to pre-fill collection name based on folder name
                if self.current_new_collection_popup and hasattr(self.current_new_collection_popup.ids, 'collection_name_input'):
                    base_folder_name = os.path.basename(self.selected_folder_path)
                    self.current_new_collection_popup.ids.collection_name_input.text = base_folder_name
                    self.current_new_collection_popup.ids.collection_name_input.hint_text = "Name based on folder"

        folder_popup_instance.dismiss()

    def get_selected_folder_path(self):
        """
        Returns the currently selected folder path.
        """
        return self.selected_folder_path 

    def open_image_chooser_popup(self):
        """
        Opens a popup dialog for the user to select an image for the new collection.
        """
        image_popup = ImageChooserPopup()
        image_popup.open()

    def select_image(self, selection, image_popup_instance):
        """
        Handles the selection of an image from the ImageChooserPopup.
        Updates the selected image path and the preview image in the NewCollectionPopup.
        Args:
            selection (list): A list containing the path(s) of the selected image(s).
                              Expected to contain one image path.
            image_popup_instance: The instance of the ImageChooserPopup.
        """
        if selection: 
            self.selected_image_path = selection[0]
            print(f"Selected image: {self.selected_image_path}")
            if self.current_new_collection_popup and hasattr(self.current_new_collection_popup.ids, 'image_preview'):
                self.current_new_collection_popup.ids.image_preview.source = self.selected_image_path
                self.current_new_collection_popup.ids.image_preview.reload() 
            else:
                print("Error: 'image_preview' not found in NewCollectionPopup ids or popup not available.")
        image_popup_instance.dismiss()

    def save_collection(self, nom, new_collection_popup_instance): 
        """
        Saves a new collection to the database.
        Retrieves the name, selected image, selected folder, and tags.
        Performs validation and provides feedback to the user.
        Args:
            nom (str): The name of the new collection.
            new_collection_popup_instance: The instance of the NewCollectionPopup.
        """
        print(f"Attempting to save collection: {nom}")
        nom_collection = nom.strip() 

        if not nom_collection:
            print("Collection name cannot be empty.")
            if hasattr(new_collection_popup_instance.ids, 'feedback_label'): # Assuming feedback_label exists
                new_collection_popup_instance.ids.feedback_label.text = "Collection name cannot be empty."
            return

        if not self.selected_folder_path:
            print("Folder path cannot be empty.")
            if hasattr(new_collection_popup_instance.ids, 'feedback_label'):
                new_collection_popup_instance.ids.feedback_label.text = "Please select a folder."
            return

        if not self.selected_image_path:
            print("Cover image path cannot be empty.")
            if hasattr(new_collection_popup_instance.ids, 'feedback_label'):
                new_collection_popup_instance.ids.feedback_label.text = "Please select a cover image."
            return

        tags_string = ",".join(self.selected_tags_for_new_collection)

        collection_id = add_collection_to_db(nom_collection, self.selected_folder_path, self.selected_image_path, tags_string)

        if collection_id:
            print(f"Collection '{nom_collection}' added successfully with ID: {collection_id}")
            if hasattr(new_collection_popup_instance.ids, 'feedback_label'):
                new_collection_popup_instance.ids.feedback_label.text = f"Collection '{nom_collection}' added successfully."
            new_collection_popup_instance.dismiss()
            self.populate_collections_grid()
        else:
            print(f"Error saving collection '{nom_collection}'.")
            if hasattr(new_collection_popup_instance.ids, 'feedback_label'):
                new_collection_popup_instance.ids.feedback_label.text = "Error saving collection."

    def populate_collections_grid(self):
        """
        Populates the main grid layout with CollectionCard widgets
        for each collection retrieved from the database.
        """
        grid = self.root.ids.get('collections_grid')
        if not grid:
            print("Error: collections_grid not found in root ids.")
            return

        grid.clear_widgets()
        collections_data = get_all_collections() # Va maintenant retourner (id, nom, img, path, tags)

        if not collections_data:
            print("No collections found in the database to display.")
            # TODO: Afficher un message à l'utilisateur dans l'interface
            return

        for coll_id, nom, image_path_from_db, folder_path_from_db, tags_concatenes in collections_data:
            card = CollectionCard(
                collection_id=coll_id,
                collection_name=nom,
                image_source=str(image_path_from_db),
                collection_tags=str(tags_concatenes if tags_concatenes else ""),
                folder_path=str(folder_path_from_db if folder_path_from_db else "") # Passer le chemin du dossier
            )
            grid.add_widget(card)
        print(f"Populated grid with {len(collections_data)} collections.")

    def open_collection_folder(self, folder_path):
        """
        Opens the folder associated with a collection in the system's file explorer.
        Args:
            folder_path (str): The path of the folder to open.
        """
        if not folder_path or not os.path.isdir(folder_path):
            print(f"Error: Folder path is invalid or does not exist: {folder_path}")
            # Optionnel: Afficher un message à l'utilisateur
            # par exemple, via un popup d'erreur ou un label dans l'interface.
            return

        try:
            if os.name == 'nt': # Windows
                os.startfile(folder_path)
            elif sys.platform == 'darwin': # macOS
                subprocess.Popen(['open', folder_path])
            else: # Linux et autres Unix
                subprocess.Popen(['xdg-open', folder_path])
            print(f"Attempting to open folder: {folder_path}")
        except Exception as e:
            print(f"Failed to open folder {folder_path}: {e}")
            # Optionnel: Afficher un message d'erreur à l'utilisateur.

if __name__ == '__main__':
    initialize_database()
    VisualCollectionApp().run()