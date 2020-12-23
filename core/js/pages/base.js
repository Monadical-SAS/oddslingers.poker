/* This is loaded when no JS component is set on a React request handler.
   It can be used to display simple messages by passing:

    global.props.body="text here"
    global.props.className="alert-success"
      or
    global.props.error="short error summary"
    global.props.details="error details or traceback"
*/

import React from 'react'
import ReactDOM from 'react-dom'

ReactDOM.render(
    <div {...global.props}>
        {global.props.error ?
            <div className="alert alert-danger empty-response">
                <b>An error occured while rendering the page.</b><br/><br/>
                {global.props.error}<br/><hr/>
                {global.props.details ?
                    <pre>{global.props.details}</pre>
                  : 'Sorry! Try refreshing and check your setup.'
                }
            </div>
          : (global.props.body ?
                <div id="plain-react-body">
                    {global.props.body.split('\n').map(line =>
                        <div>{line}</div>)}
                </div>
              : <div className="alert alert-danger empty-response">
                    No JS file was given to render this page,
                    check the value of <b>RequestHandler.component</b>.
                </div>)
        }
    </div>,
    global.react_mount
)
